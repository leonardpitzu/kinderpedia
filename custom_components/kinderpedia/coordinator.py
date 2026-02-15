import logging
import re
from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from .api import KinderpediaAPI

_LOGGER = logging.getLogger(__name__)

_FOOD_TYPE_MAP = {"md": "breakfast", "mp": "lunch", "mp2": "lunch", "g": "snack"}
_NAP_PATTERN = re.compile(r"\s*(\d+)\s*h\s*and\s*(\d+)\s*min")
_NAP_PATTERN_MIN = re.compile(r"\s*(\d+)\s*min")


def _parse_timeline(json_data):
    """Parse raw timeline JSON into a weekday-keyed dict of day data."""
    parsed = {}
    weekday_map = ["monday", "tuesday", "wednesday", "thursday", "friday"]

    try:
        days = {}
        if isinstance(json_data, dict):
            result = json_data.get("result")
            if isinstance(result, dict):
                dailytimeline = result.get("dailytimeline")
                if isinstance(dailytimeline, dict):
                    days = dailytimeline.get("days", {})

        sorted_day_items = sorted(days.items())
        for i, weekday in enumerate(weekday_map):
            if i < len(sorted_day_items):
                date_key, day_data = sorted_day_items[i]
                day_data = day_data or {}

                day_entry = {
                    "name": weekday,
                    "date": date_key,
                    "checkin": "unknown",
                    "nap": "unknown"
                }

                for item in day_data.get("data", []) or []:
                    item_id = item.get("id", "")
                    if item_id == "checkin":
                        day_entry["checkin"] = item.get("subtitle", "unknown")
                    elif item_id == "nap":
                        day_entry["nap"] = item.get("subtitle", "unknown")
                        if day_entry["nap"] != "unknown":
                            match = _NAP_PATTERN.search(day_entry["nap"])
                            if match:
                                hours = int(match.group(1))
                                minutes = int(match.group(2))
                                day_entry["nap_duration"] = hours * 60 + minutes
                            else:
                                match_min = _NAP_PATTERN_MIN.search(day_entry["nap"])
                                if match_min:
                                    day_entry["nap_duration"] = int(match_min.group(1))
                                else:
                                    day_entry["nap_duration"] = 0
                    elif item_id.startswith("food_"):
                        details = item.get("details")
                        if isinstance(details, dict):
                            food = details.get("food") or {}
                            meals = food.get("meals", []) or []

                            lunch_percents = []

                            for meal in meals:
                                food_type = _FOOD_TYPE_MAP.get(meal.get("type", "unknown"), meal.get("type", "unknown"))
                                percent = meal.get("percent")
                                if meal.get("type") in ["mp", "mp2"] and isinstance(percent, (int, float)):
                                    lunch_percents.append(percent)

                                menus = meal.get("menus", []) or []
                                if menus:
                                    day_entry[f"{food_type}_items"] = [m.get("name", "unknown") for m in menus]
                                    totals = meal.get("totals", {}) or {}
                                    day_entry[f"{food_type}_kcal"] = totals.get("kcal", 0)
                                    day_entry[f"{food_type}_weight"] = totals.get("weight", 0)

                                if meal.get("type") not in ["mp", "mp2"]:
                                    day_entry[f"{food_type}_percent"] = percent if percent is not None else 0
                                else:
                                    if lunch_percents:
                                        day_entry["lunch_percent"] = round(sum(lunch_percents) / len(lunch_percents), 1)
                                    else:
                                        day_entry["lunch_percent"] = 0

                parsed[weekday] = day_entry
            else:
                parsed[weekday] = {
                    "name": weekday,
                    "date": "unknown",
                    "checkin": "unknown",
                    "nap": "unknown",
                    "nap_duration": 0,
                    "breakfast_items": [],
                    "breakfast_kcal": 0,
                    "breakfast_weight": 0,
                    "breakfast_percent": 0,
                    "lunch_items": [],
                    "lunch_kcal": 0,
                    "lunch_weight": 0,
                    "lunch_percent": 0,
                    "snack_items": [],
                    "snack_kcal": 0,
                    "snack_weight": 0,
                    "snack_percent": 0,
                }

    except Exception as e:
        _LOGGER.error("Error parsing kinderpedia timeline: %s", e)

    return parsed


class KinderpediaDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, api: KinderpediaAPI) -> None:
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            name="Kinderpedia Coordinator",
            update_interval=timedelta(minutes=15),
        )

    async def _async_update_data(self):
        """Fetch all children and their timelines, return parsed data."""
        _LOGGER.debug("Fetching data from Kinderpedia API")
        try:
            children = await self.api.fetch_children()
            result = {
                "children": {},
                "last_updated": utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            }

            for child in children:
                child_id = child["child_id"]
                kg_id = child["kindergarten_id"]
                key = f"{child_id}_{kg_id}"

                timeline_raw = await self.api.fetch_timeline(child_id, kg_id)
                _LOGGER.debug("Kinderpedia: Raw timeline for %s: %s", key, timeline_raw)
                parsed_days = _parse_timeline(timeline_raw)

                result["children"][key] = {
                    "child": child,
                    "days": parsed_days,
                }

            _LOGGER.debug("Kinderpedia data successfully fetched for %d children", len(children))
            return result
        except Exception as err:
            _LOGGER.error("Failed to fetch Kinderpedia data: %s", err)
            raise UpdateFailed(f"Error fetching data: {err}") from err
