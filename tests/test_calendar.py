"""Tests for Kinderpedia calendar platform."""

from datetime import date, datetime, time
from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

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


# -------------------------------------------------------------------
# Event building
# -------------------------------------------------------------------

async def test_calendar_builds_timed_school_events(hass: HomeAssistant):
    """School events must be timed (datetime start/end), not all-day."""
    coordinator = MagicMock()
    coordinator.data = _make_coordinator_data()

    cal = _make_calendar(coordinator)
    events = cal._build_events()

    school_events = [e for e in events if "School" in (e.summary or "")]
    assert len(school_events) >= 1

    monday_school = [e for e in school_events if e.summary == "School" and isinstance(e.start, datetime) and e.start.date() == date(2026, 2, 9)]
    assert len(monday_school) == 1
    ev = monday_school[0]

    # Must be timed, not all-day
    assert isinstance(ev.start, datetime)
    assert isinstance(ev.end, datetime)
    assert ev.start.hour == 8
    assert ev.start.minute == 15
    # End at 18:00
    assert ev.end.hour == 18
    assert ev.end.minute == 0


async def test_calendar_school_event_has_tz(hass: HomeAssistant):
    """Timed school events must carry timezone info."""
    coordinator = MagicMock()
    coordinator.data = _make_coordinator_data()

    cal = _make_calendar(coordinator)
    events = cal._build_events()

    school_events = [e for e in events if "School" in (e.summary or "")]
    for ev in school_events:
        if isinstance(ev.start, datetime):
            assert ev.start.tzinfo is not None
            assert ev.end.tzinfo is not None


async def test_calendar_nap_event_unchanged(hass: HomeAssistant):
    """Nap events still use actual nap start/end times."""
    coordinator = MagicMock()
    coordinator.data = _make_coordinator_data()

    cal = _make_calendar(coordinator)
    events = cal._build_events()

    nap_events = [e for e in events if e.summary == "Nap"]
    assert len(nap_events) == 1
    nap = nap_events[0]
    assert isinstance(nap.start, datetime)
    assert isinstance(nap.end, datetime)
    assert nap.start.hour == 12 and nap.start.minute == 39
    assert nap.end.hour == 14 and nap.end.minute == 33
    assert nap.start.tzinfo is not None


async def test_calendar_event_description_has_emoji_meals(hass: HomeAssistant):
    """Event description uses emoji-prefixed meal lines."""
    coordinator = MagicMock()
    coordinator.data = _make_coordinator_data()

    cal = _make_calendar(coordinator)
    events = cal._build_events()

    monday_school = [
        e for e in events
        if isinstance(e.start, datetime) and e.start.date() == date(2026, 2, 9) and "School" in (e.summary or "")
    ]
    assert len(monday_school) == 1

    desc = monday_school[0].description or ""
    assert "🥣" in desc  # breakfast icon
    assert "Breakfast" in desc
    assert "Cereal" in desc
    assert "🍽️" in desc  # lunch icon
    assert "Chicken soup" in desc
    assert "🍪" in desc  # snack icon
    assert "Apple" in desc

    # Percent shown
    assert "(80%)" in desc  # breakfast 80%
    assert "(90" in desc  # lunch 90% (may be 90.0% due to averaging)

    # Check-in and Nap must NOT appear in description
    assert "Check-in" not in desc
    assert "Nap" not in desc


# -------------------------------------------------------------------
# .event property
# -------------------------------------------------------------------

async def test_calendar_event_property_returns_today(hass: HomeAssistant):
    """The .event property returns an event for today if one exists."""
    coordinator = MagicMock()
    data = _make_coordinator_data()

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


# -------------------------------------------------------------------
# async_get_events range filtering
# -------------------------------------------------------------------

async def test_calendar_async_get_events_filters_range(hass: HomeAssistant):
    """async_get_events should filter by the requested date range."""
    coordinator = MagicMock()
    coordinator.data = _make_coordinator_data()

    cal = _make_calendar(coordinator)

    start = datetime(2026, 2, 9)
    end = datetime(2026, 2, 10)

    events = await cal.async_get_events(hass, start, end)
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
    assert len(events) >= 2


# -------------------------------------------------------------------
# extra_state_attributes
# -------------------------------------------------------------------

async def test_calendar_extra_state_attributes_today(hass: HomeAssistant):
    """Calendar entity exposes today's day data as attributes when today has data."""
    coordinator = MagicMock()
    data = _make_coordinator_data()

    # Force Monday to be today
    today_str = date.today().isoformat()
    data["children"]["111_222"]["days"]["monday"]["date"] = today_str

    coordinator.data = data
    cal = _make_calendar(coordinator)
    attrs = cal.extra_state_attributes

    assert "checkin" in attrs
    assert "last_updated" in attrs
    assert attrs["checkin"] == "08:15 - 16:30"
    assert "breakfast_items" in attrs
    assert "Cereal" in attrs["breakfast_items"]
    assert "breakfast_percent" in attrs
    assert attrs["breakfast_percent"] == 80
    assert attrs["date"] == today_str


async def test_calendar_extra_state_attributes_falls_back_to_latest(hass: HomeAssistant):
    """When today is not in the data, attributes show the most recent school day."""
    coordinator = MagicMock()
    data = _make_coordinator_data()
    # All dates are 2026-02-09..13 (in the past) — none match today
    coordinator.data = data
    cal = _make_calendar(coordinator)
    attrs = cal.extra_state_attributes

    # Monday (2026-02-09) is the only day with real activity in MOCK_TIMELINE_RAW
    assert attrs.get("date") == "2026-02-09"
    assert "checkin" in attrs
    assert attrs["checkin"] == "08:15 - 16:30"
    assert "breakfast_items" in attrs
    assert "Cereal" in attrs["breakfast_items"]


async def test_calendar_extra_state_attributes_skips_empty_days(hass: HomeAssistant):
    """Days with no checkin or meals are not returned as the latest day."""
    coordinator = MagicMock()
    data = _make_coordinator_data()
    # Wipe Monday's activity
    data["children"]["111_222"]["days"]["monday"]["checkin"] = "unknown"
    data["children"]["111_222"]["days"]["monday"].pop("breakfast_items", None)
    data["children"]["111_222"]["days"]["monday"].pop("lunch_items", None)
    data["children"]["111_222"]["days"]["monday"].pop("snack_items", None)
    coordinator.data = data
    cal = _make_calendar(coordinator)
    # With all activity removed from the only data-rich day, attrs should be empty
    assert cal.extra_state_attributes == {}


# -------------------------------------------------------------------
# Edge cases
# -------------------------------------------------------------------

async def test_calendar_no_data(hass: HomeAssistant):
    """No crash when coordinator data is empty."""
    coordinator = MagicMock()
    coordinator.data = None

    cal = _make_calendar(coordinator)
    assert cal.event is None
    events = await cal.async_get_events(hass, datetime(2026, 2, 9), datetime(2026, 2, 14))
    assert events == []
    assert cal.extra_state_attributes == {}


async def test_nap_event_not_created_without_times(hass: HomeAssistant):
    """When nap subtitle has only duration (no times), no nap event is created."""
    coordinator = MagicMock()
    data = _make_coordinator_data()
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
        "12:39 - ",
        "12:39 -",
        "12:39",
        "12:39 - , 1 h",
        " - 14:33",
    ]
    for nap_text in partial_values:
        days["nap"] = nap_text
        coordinator.data = data

        cal = _make_calendar(coordinator)
        events = cal._build_events()

        nap_events = [e for e in events if e.summary == "Nap"]
        assert len(nap_events) == 0, f"Nap event should not be created for: {nap_text!r}"


async def test_school_event_no_checkin_uses_fallback(hass: HomeAssistant):
    """School event without valid checkin time starts at 08:00 (fallback)."""
    coordinator = MagicMock()
    data = _make_coordinator_data()
    data["children"]["111_222"]["days"]["monday"]["checkin"] = "unknown"
    coordinator.data = data

    cal = _make_calendar(coordinator)
    events = cal._build_events()

    monday_school = [
        e for e in events
        if isinstance(e.start, datetime) and e.start.date() == date(2026, 2, 9) and "School" in (e.summary or "")
    ]
    assert len(monday_school) == 1
    ev = monday_school[0]
    assert ev.start.hour == 8
    assert ev.start.minute == 0
    assert ev.end.hour == 18
    assert ev.end.minute == 0


async def test_parse_checkin_time():
    """_parse_checkin_time extracts HH:MM from various checkin formats."""
    assert KinderpediaCalendar._parse_checkin_time("07:40 - by Alina Vieriu") == time(7, 40)
    assert KinderpediaCalendar._parse_checkin_time("08:15 - 16:30") == time(8, 15)
    assert KinderpediaCalendar._parse_checkin_time("unknown") is None
    assert KinderpediaCalendar._parse_checkin_time("") is None
    assert KinderpediaCalendar._parse_checkin_time("Not completed") is None


# -------------------------------------------------------------------
# Absence handling
# -------------------------------------------------------------------

async def test_absent_day_has_no_school_event(hass: HomeAssistant):
    """When a child is absent, no School event should be created for that day."""
    coordinator = MagicMock()
    data = _make_coordinator_data()

    # Mark Monday as absent (but keep meal data — the menu is still published)
    data["children"]["111_222"]["days"]["monday"]["absent"] = True
    data["children"]["111_222"]["days"]["monday"]["checkin"] = "Absent"
    data["children"]["111_222"]["days"]["monday"]["absence_reason"] = "vacation"

    coordinator.data = data
    cal = _make_calendar(coordinator)
    events = cal._build_events()

    monday_events = [
        e for e in events
        if isinstance(e.start, datetime) and e.start.date() == date(2026, 2, 9)
    ]
    assert len(monday_events) == 0, "No events should be created for an absent day"


async def test_absent_day_has_no_nap_event(hass: HomeAssistant):
    """When a child is absent, no Nap event should be created either."""
    coordinator = MagicMock()
    data = _make_coordinator_data()

    data["children"]["111_222"]["days"]["monday"]["absent"] = True
    data["children"]["111_222"]["days"]["monday"]["checkin"] = "Absent"

    coordinator.data = data
    cal = _make_calendar(coordinator)
    events = cal._build_events()

    nap_events = [e for e in events if e.summary == "Nap"]
    assert len(nap_events) == 0, "No nap event for an absent day"


async def test_non_absent_day_still_has_school_event(hass: HomeAssistant):
    """Days without the absent flag should still produce events normally."""
    coordinator = MagicMock()
    data = _make_coordinator_data()
    # Ensure absent is not set
    data["children"]["111_222"]["days"]["monday"].pop("absent", None)

    coordinator.data = data
    cal = _make_calendar(coordinator)
    events = cal._build_events()

    monday_school = [
        e for e in events
        if isinstance(e.start, datetime) and e.start.date() == date(2026, 2, 9) and e.summary == "School"
    ]
    assert len(monday_school) == 1
