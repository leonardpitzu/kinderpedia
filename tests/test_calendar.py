"""Tests for Kinderpedia calendar platform."""

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.kinderpedia.const import DOMAIN
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
    # Should only include the Monday event (2026-02-09)
    assert all(e.start >= date(2026, 2, 9) for e in events)
    assert all(e.start < date(2026, 2, 10) for e in events)


async def test_calendar_async_get_events_full_week(hass: HomeAssistant):
    """Requesting the full week should return events for days with data."""
    coordinator = MagicMock()
    coordinator.data = _make_coordinator_data()

    cal = _make_calendar(coordinator)

    start = datetime(2026, 2, 9)
    end = datetime(2026, 2, 14)

    events = await cal.async_get_events(hass, start, end)
    # Monday has real data, other days have empty data arrays
    # Only Monday should produce events (the only one with checkin/food)
    assert len(events) >= 1


async def test_calendar_no_data(hass: HomeAssistant):
    """No crash when coordinator data is empty."""
    coordinator = MagicMock()
    coordinator.data = None

    cal = _make_calendar(coordinator)
    assert cal.event is None
    events = await cal.async_get_events(hass, datetime(2026, 2, 9), datetime(2026, 2, 14))
    assert events == []


async def test_calendar_event_description_contains_meals(hass: HomeAssistant):
    """Event description should mention meals."""
    coordinator = MagicMock()
    coordinator.data = _make_coordinator_data()

    cal = _make_calendar(coordinator)
    events = cal._build_events()

    monday_events = [e for e in events if e.start == date(2026, 2, 9)]
    assert len(monday_events) == 1

    desc = monday_events[0].description or ""
    assert "Breakfast" in desc
    assert "Lunch" in desc
    assert "Cereal" in desc
    assert "Chicken soup" in desc
