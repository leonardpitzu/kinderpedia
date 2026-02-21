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


def _parse_newsfeed(json_data):
    """Parse raw newsfeed JSON into a list of feed items."""
    items = []
    try:
        if not isinstance(json_data, dict):
            return items

        result = json_data.get("result")
        if not isinstance(result, dict):
            return items

        feed = result.get("feed")
        if not isinstance(feed, list):
            return items

        for entry in feed:
            item_type = entry.get("type", "unknown")
            content = entry.get("content") or {}
            stats = entry.get("stats") or {}

            # Extract gallery info
            gallery = content.get("gallery") or {}
            images = gallery.get("images") or []
            image_count = gallery.get("count_all", len(images))
            first_image = images[0].get("fullsize") if images else None

            # Extract video info
            video = content.get("video") or {}
            video_url = video.get("url")

            # Extract file/invoice info
            file_info = content.get("file") or {}
            file_url = file_info.get("src")

            # Latest comment
            latest_comments = entry.get("latest_comments") or []
            latest_comment = None
            if latest_comments:
                c = latest_comments[0]
                latest_comment = {
                    "author": c.get("sender_name"),
                    "text": c.get("comment"),
                    "date": c.get("date_friendly"),
                }

            parsed_item = {
                "id": entry.get("id"),
                "type": item_type,
                "title": content.get("title") or entry.get("title") or "",
                "description": content.get("description") or "",
                "date": entry.get("date"),
                "date_friendly": entry.get("date_friendly"),
                "author": f"{(entry.get('user') or {}).get('first_name', '')} {(entry.get('user') or {}).get('last_name', '')}".strip(),
                "likes": stats.get("likes", 0),
                "comments": stats.get("comments", 0),
                "image_count": image_count if images else 0,
                "first_image_url": first_image,
                "video_url": video_url,
                "file_url": file_url,
                "latest_comment": latest_comment,
                "group": None,
            }

            # Extract group info
            groups = entry.get("groups") or []
            if groups:
                parsed_item["group"] = groups[0].get("name")

            # Invoice-specific fields
            if item_type == "invoice":
                parsed_item["invoice_subtitle1"] = content.get("subtitle1")
                parsed_item["invoice_subtitle2"] = content.get("subtitle2")

            items.append(parsed_item)

    except Exception as e:
        _LOGGER.error("Error parsing kinderpedia newsfeed: %s", e)

    return items


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

                newsfeed_raw = await self.api.fetch_newsfeed(child_id, kg_id)
                _LOGGER.debug("Kinderpedia: Raw newsfeed for %s: %s", key, newsfeed_raw)
                parsed_feed = _parse_newsfeed(newsfeed_raw)

                result["children"][key] = {
                    "child": child,
                    "days": parsed_days,
                    "newsfeed": parsed_feed,
                }

            _LOGGER.debug("Kinderpedia data successfully fetched for %d children", len(children))
            return result
        except Exception as err:
            _LOGGER.error("Failed to fetch Kinderpedia data: %s", err)
            raise UpdateFailed(f"Error fetching data: {err}") from err
