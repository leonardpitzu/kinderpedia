"""Calendar platform for Kinderpedia."""

import logging
import re
from datetime import date, datetime, timedelta, timezone

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_NAP_TIME_RE = re.compile(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})")


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Kinderpedia calendar entities."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = entry_data["coordinator"]

    tracked_keys: set[str] = set()

    @callback
    def _discover_new_children():
        data = coordinator.data or {}
        children_data = data.get("children", {})
        new_entities = []

        for key, child_data in children_data.items():
            if key in tracked_keys:
                continue
            tracked_keys.add(key)

            child = child_data["child"]
            child_id = child["child_id"]
            kg_id = child["kindergarten_id"]
            device_name = f"{child['first_name']} {child['last_name']}"
            first_name = child["first_name"]

            new_entities.append(
                KinderpediaCalendar(
                    coordinator, child_id, kg_id, device_name, first_name
                )
            )

        if new_entities:
            async_add_entities(new_entities)

    _discover_new_children()
    config_entry.async_on_unload(
        coordinator.async_add_listener(_discover_new_children)
    )


class KinderpediaCalendar(CoordinatorEntity, CalendarEntity):
    """Calendar showing daily school activities for a child."""

    def __init__(self, coordinator, child_id, kg_id, device_name, first_name):
        """Initialise the calendar entity."""
        super().__init__(coordinator)
        self._key = f"{child_id}_{kg_id}"
        self._attr_unique_id = f"{DOMAIN}_calendar_{child_id}_{kg_id}"
        self._attr_name = f"{first_name.lower()} school"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{child_id}_{kg_id}")},
            "name": device_name,
            "manufacturer": "Kinderpedia",
        }

    # ------------------------------------------------------------------
    # CalendarEntity interface
    # ------------------------------------------------------------------

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current/next event (today)."""
        events = self._build_events()
        today = date.today()

        def _to_date(dt_or_d: date | datetime) -> date:
            return dt_or_d.date() if isinstance(dt_or_d, datetime) else dt_or_d

        for ev in events:
            ev_start = _to_date(ev.start)
            ev_end = _to_date(ev.end)
            # All-day events have exclusive end; timed events end same day
            if ev_start <= today <= ev_end:
                return ev
        return None

    async def async_get_events(
        self,
        hass,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return events within the requested range."""
        events = self._build_events()
        start_d = start_date.date() if isinstance(start_date, datetime) else start_date
        end_d = end_date.date() if isinstance(end_date, datetime) else end_date

        def _event_date(dt_or_d: date | datetime) -> date:
            return dt_or_d.date() if isinstance(dt_or_d, datetime) else dt_or_d

        return [
            ev
            for ev in events
            if _event_date(ev.start) < end_d and _event_date(ev.end) >= start_d
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_events(self) -> list[CalendarEvent]:
        """Build calendar events from coordinator day data."""
        data = self.coordinator.data or {}
        child_data = data.get("children", {}).get(self._key, {})
        days = child_data.get("days", {})

        events: list[CalendarEvent] = []
        for _weekday, day_info in days.items():
            date_str = day_info.get("date")
            if not date_str or date_str == "unknown":
                continue

            try:
                event_date = date.fromisoformat(date_str)
            except (ValueError, TypeError):
                continue

            summary_parts: list[str] = []
            description_parts: list[str] = []

            # Check-in / check-out  (shown in event title only)
            checkin = day_info.get("checkin", "unknown")
            if checkin and checkin != "unknown":
                summary_parts.append(f"School {checkin}")

            # Nap → separate timed event
            nap = day_info.get("nap", "unknown")
            if nap and nap != "unknown":
                nap_event = self._build_nap_event(event_date, nap)
                if nap_event:
                    events.append(nap_event)

            # Meals
            for meal in ("breakfast", "lunch", "snack"):
                items = day_info.get(f"{meal}_items", [])
                pct = day_info.get(f"{meal}_percent")
                if items:
                    food_str = ", ".join(items)
                    pct_str = f" ({pct}%)" if pct else ""
                    description_parts.append(f"{meal.capitalize()}: {food_str}{pct_str}")

            if not summary_parts and not description_parts:
                continue

            summary = summary_parts[0] if summary_parts else f"School day ({_weekday})"
            description = "\n".join(description_parts) if description_parts else None

            events.append(
                CalendarEvent(
                    summary=summary,
                    start=event_date,
                    end=event_date + timedelta(days=1),
                    description=description,
                )
            )

        return events

    @staticmethod
    def _build_nap_event(
        event_date: date, nap_text: str
    ) -> CalendarEvent | None:
        """Create a timed nap event when start/end times are available."""
        match = _NAP_TIME_RE.search(nap_text)
        if not match:
            return None

        try:
            start_time = datetime.strptime(match.group(1), "%H:%M").time()
            end_time = datetime.strptime(match.group(2), "%H:%M").time()
        except ValueError:
            return None

        nap_start = datetime.combine(event_date, start_time, tzinfo=dt_util.DEFAULT_TIME_ZONE)
        nap_end = datetime.combine(event_date, end_time, tzinfo=dt_util.DEFAULT_TIME_ZONE)

        if nap_end <= nap_start:
            return None

        return CalendarEvent(
            summary="Nap",
            start=nap_start,
            end=nap_end,
        )
