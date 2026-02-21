"""Tests for Kinderpedia calendar platform."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.kinderpedia.coordinator import _parse_timeline
from custom_components.kinderpedia.calendar import KinderpediaCalendar
from tests.conftest import MOCK_CHILD, MOCK_TIMELINE_RAW


def _make_coordinator_data():
    """Build coordinator data using the shared fixtures."""
    parsed_days = _parse_timeline(MOCK_TIMELINE_RAW)
    return {
        "last_updated": "2026-02-21 12:00:00",
        "children": {
            "111_222": {
                "child": dict(MOCK_CHILD),
                "days": parsed_days,
            }
        },
    }


def _make_calendar(coordinator) -> KinderpediaCalendar:
    """Create a calendar entity wired to a mock coordinator."""
    cal = KinderpediaCalendar(
        coordinator,
        child_id=111,
        kg_id=222,
        device_name="Alice Smith",
        first_name="Alice",
    )
    return cal


async def test_calendar_builds_events(hass: HomeAssistant):
    """Events are created from day data."""
    coordinator = MagicMock()
    coordinator.data = _make_coordinator_data()

    cal = _make_calendar(coordinator)
    events = cal._build_events()

    # The mock timeline has 5 days; only Monday has meaningful data.
    has_checkin_event = any("08:15" in (e.summary or "") for e in events)
    assert has_checkin_event

    # Monday should also produce a timed nap event
    nap_events = [e for e in events if e.summary == "Nap"]
    assert len(nap_events) == 1
    nap = nap_events[0]
    assert isinstance(nap.start, datetime)
    assert isinstance(nap.end, datetime)
    assert nap.start.hour == 12 and nap.start.minute == 39
    assert nap.end.hour == 14 and nap.end.minute == 33
    assert nap.start.tzinfo is not None


async def test_calendar_event_property_returns_today(hass: HomeAssistant):
    """The .event property returns an event for today if one exists."""
    coordinator = MagicMock()
    data = _make_coordinator_data()

    # Patch one day to be today so the property picks it up
    today_str = date.today().isoformat()
    today_weekday = date.today().strftime("%A").lower()
    days = data["children"]["111_222"]["days"]
    if today_weekday in days:
        days[today_weekday]["date"] = today_str
        days[today_weekday]["checkin"] = "08:00 - 16:00"

    coordinator.data = data
    cal = _make_calendar(coordinator)
    ev = cal.event

    if today_weekday in days and days[today_weekday].get("date") == today_str:
        assert ev is not None
    # If today isn't a weekday in the data, event can be None – still valid


async def test_calendar_async_get_events_filters_range(hass: HomeAssistant):
    """async_get_events should filter by the requested date range."""
    coordinator = MagicMock()
    coordinator.data = _make_coordinator_data()

    cal = _make_calendar(coordinator)

    # The mock dates are 2026-02-09 .. 2026-02-13
    start = datetime(2026, 2, 9)
    end = datetime(2026, 2, 10)

    events = await cal.async_get_events(hass, start, end)
    # Should only include Monday events (2026-02-09): school + nap
    for e in events:
        ev_date = e.start.date() if isinstance(e.start, datetime) else e.start
        assert ev_date >= date(2026, 2, 9)
        assert ev_date < date(2026, 2, 10)


async def test_calendar_async_get_events_full_week(hass: HomeAssistant):
    """Requesting the full week should return events for days with data."""
    coordinator = MagicMock()
    coordinator.data = _make_coordinator_data()

    cal = _make_calendar(coordinator)

    start = datetime(2026, 2, 9)
    end = datetime(2026, 2, 14)

    events = await cal.async_get_events(hass, start, end)
    # Monday has real data, other days have empty data arrays
    # Monday should produce a school event + a nap event
    assert len(events) >= 2


async def test_calendar_no_data(hass: HomeAssistant):
    """No crash when coordinator data is empty."""
    coordinator = MagicMock()
    coordinator.data = None

    cal = _make_calendar(coordinator)
    assert cal.event is None
    events = await cal.async_get_events(hass, datetime(2026, 2, 9), datetime(2026, 2, 14))
    assert events == []


async def test_calendar_event_description_contains_meals(hass: HomeAssistant):
    """Event description should mention meals but not checkin/nap."""
    coordinator = MagicMock()
    coordinator.data = _make_coordinator_data()

    cal = _make_calendar(coordinator)
    events = cal._build_events()

    monday_events = [e for e in events if isinstance(e.start, date) and not isinstance(e.start, datetime) and e.start == date(2026, 2, 9)]
    assert len(monday_events) == 1

    desc = monday_events[0].description or ""
    assert "Breakfast" in desc
    assert "Lunch" in desc
    assert "Cereal" in desc
    assert "Chicken soup" in desc

    # Check-in and Nap must NOT appear in description
    assert "Check-in" not in desc
    assert "Nap" not in desc


async def test_nap_event_not_created_without_times(hass: HomeAssistant):
    """When nap subtitle has only duration (no times), no nap event is created."""
    coordinator = MagicMock()
    data = _make_coordinator_data()
    # Override nap to duration-only format
    data["children"]["111_222"]["days"]["monday"]["nap"] = "1 h and 30 min"
    coordinator.data = data

    cal = _make_calendar(coordinator)
    events = cal._build_events()

    nap_events = [e for e in events if e.summary == "Nap"]
    assert len(nap_events) == 0


async def test_nap_event_not_created_with_partial_times(hass: HomeAssistant):
    """When nap has a start time but no end time (API glitch), no nap event."""
    coordinator = MagicMock()
    data = _make_coordinator_data()
    days = data["children"]["111_222"]["days"]["monday"]

    partial_values = [
        "12:39 - ",         # end time missing entirely
        "12:39 -",          # trailing dash, no end
        "12:39",            # bare start, no separator
        "12:39 - , 1 h",   # comma where end time should be
        " - 14:33",         # start time missing
    ]
    for nap_text in partial_values:
        days["nap"] = nap_text
        coordinator.data = data

        cal = _make_calendar(coordinator)
        events = cal._build_events()

        nap_events = [e for e in events if e.summary == "Nap"]
        assert len(nap_events) == 0, f"Nap event should not be created for: {nap_text!r}"
