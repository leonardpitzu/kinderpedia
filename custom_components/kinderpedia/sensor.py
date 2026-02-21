import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = entry_data["coordinator"]

    tracked_keys = set()

    @callback
    def _discover_new_children():
        """Create sensors for newly discovered children."""
        data = coordinator.data or {}
        children_data = data.get("children", {})
        new_sensors = []

        for key, child_data in children_data.items():
            if key in tracked_keys:
                continue
            tracked_keys.add(key)

            child = child_data["child"]
            child_id = child["child_id"]
            kg_id = child["kindergarten_id"]
            device_name = f"{child['first_name']} {child['last_name']}"
            first_name = child["first_name"]

            new_sensors.append(KinderpediaChildInfoSensor(
                coordinator, child_id, kg_id, device_name, first_name
            ))
            new_sensors.append(KinderpediaBreakfastWeekSensor(
                coordinator, child_id, kg_id, device_name, first_name
            ))
            new_sensors.append(KinderpediaLunchWeekSensor(
                coordinator, child_id, kg_id, device_name, first_name
            ))
            new_sensors.append(KinderpediaNapWeekSensor(
                coordinator, child_id, kg_id, device_name, first_name
            ))
            new_sensors.append(KinderpediaNewsfeedSensor(
                coordinator, child_id, kg_id, device_name, first_name
            ))

            for weekday in child_data.get("days", {}):
                new_sensors.append(KinderpediaDaySensor(
                    coordinator, child_id, kg_id, weekday, device_name, first_name
                ))

        if new_sensors:
            async_add_entities(new_sensors)

    _discover_new_children()
    config_entry.async_on_unload(
        coordinator.async_add_listener(_discover_new_children)
    )

class KinderpediaChildInfoSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, child_id, kg_id, device_name, first_name):
        super().__init__(coordinator)
        self._key = f"{child_id}_{kg_id}"
        self._attr_unique_id = f"{DOMAIN}_child_info_{child_id}_{kg_id}"
        self._attr_name = f"{first_name.lower()}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{child_id}_{kg_id}")},
            "name": device_name,
            "manufacturer": "Kinderpedia",
        }

    @property
    def native_value(self):
        child_data = self._get_child_data()
        if child_data:
            child = child_data["child"]
            return f"{child.get('first_name', '')} {child.get('last_name', '')}".strip()
        return None

    @property
    def extra_state_attributes(self):
        child_data = self._get_child_data()
        if not child_data:
            return {}
        child = child_data["child"]
        data = self.coordinator.data or {}
        return {
            "birth_date": child.get("birth_date"),
            "gender": "female" if child.get("gender") == "f" else "male",
            "kindergarten": child.get("kindergarten_name"),
            "last_updated": data.get("last_updated"),
        }

    def _get_child_data(self):
        data = self.coordinator.data or {}
        return data.get("children", {}).get(self._key)


class KinderpediaDaySensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, child_id, kg_id, weekday_key, device_name, first_name):
        super().__init__(coordinator)
        self._key = f"{child_id}_{kg_id}"
        self._weekday = weekday_key
        self._attr_unique_id = f"{DOMAIN}_day_{child_id}_{kg_id}_{weekday_key}"
        self._attr_name = f"{first_name.lower()} {weekday_key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{child_id}_{kg_id}")},
            "name": device_name,
            "manufacturer": "Kinderpedia",
        }

    @property
    def native_value(self):
        day_info = self._get_day_info()
        return day_info.get("name", self._weekday.capitalize())

    @property
    def extra_state_attributes(self):
        day_info = self._get_day_info()
        data = self.coordinator.data or {}
        attrs = {
            "date": day_info.get("date"),
            "last_updated": data.get("last_updated"),
        }
        for key, val in day_info.items():
            if key not in ["name", "date"]:
                attrs[key] = val
        return attrs

    def _get_day_info(self):
        data = self.coordinator.data or {}
        child_data = data.get("children", {}).get(self._key, {})
        return child_data.get("days", {}).get(self._weekday, {})


class _KinderpediaWeekSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for weekly aggregate sensors."""

    _attr_field: str = ""  # override in subclass

    def __init__(self, coordinator, child_id, kg_id, device_name, first_name, sensor_type):
        super().__init__(coordinator)
        self._key = f"{child_id}_{kg_id}"
        self._attr_unique_id = f"{DOMAIN}_{sensor_type}_{child_id}_{kg_id}"
        self._attr_name = f"{first_name.lower()} {sensor_type.replace('_', ' ')}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{child_id}_{kg_id}")},
            "name": device_name,
            "manufacturer": "Kinderpedia",
        }

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        return data.get("last_updated", "")[:10]  # date portion

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        child_data = data.get("children", {}).get(self._key, {})
        days = child_data.get("days", {})
        attrs = {
            "last_updated": data.get("last_updated"),
        }
        for weekday in ["monday", "tuesday", "wednesday", "thursday", "friday"]:
            attrs[weekday] = days.get(weekday, {}).get(self._attr_field, 0)
        return attrs


class KinderpediaBreakfastWeekSensor(_KinderpediaWeekSensorBase):
    _attr_field = "breakfast_percent"

    def __init__(self, coordinator, child_id, kg_id, device_name, first_name):
        super().__init__(coordinator, child_id, kg_id, device_name, first_name, "breakfast_week")


class KinderpediaLunchWeekSensor(_KinderpediaWeekSensorBase):
    _attr_field = "lunch_percent"

    def __init__(self, coordinator, child_id, kg_id, device_name, first_name):
        super().__init__(coordinator, child_id, kg_id, device_name, first_name, "lunch_week")


class KinderpediaNapWeekSensor(_KinderpediaWeekSensorBase):
    _attr_field = "nap_duration"

    def __init__(self, coordinator, child_id, kg_id, device_name, first_name):
        super().__init__(coordinator, child_id, kg_id, device_name, first_name, "nap_week")


class KinderpediaNewsfeedSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing the latest newsfeed activity for a child."""

    def __init__(self, coordinator, child_id, kg_id, device_name, first_name):
        super().__init__(coordinator)
        self._key = f"{child_id}_{kg_id}"
        self._attr_unique_id = f"{DOMAIN}_newsfeed_{child_id}_{kg_id}"
        self._attr_name = f"{first_name.lower()} newsfeed"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{child_id}_{kg_id}")},
            "name": device_name,
            "manufacturer": "Kinderpedia",
        }

    def _get_feed(self):
        data = self.coordinator.data or {}
        child_data = data.get("children", {}).get(self._key, {})
        return child_data.get("newsfeed", [])

    @property
    def native_value(self):
        feed = self._get_feed()
        if feed:
            return feed[0].get("summary", "")[:255]
        return None

    @property
    def extra_state_attributes(self):
        feed = self._get_feed()
        data = self.coordinator.data or {}
        attrs = {
            "last_updated": data.get("last_updated"),
        }
        if feed:
            latest = feed[0]
            attrs["latest_date"] = latest.get("date")

            # Recent items as compact text summaries
            attrs["recent"] = [
                {
                    "summary": item.get("summary", ""),
                    "date": item.get("date", ""),
                }
                for item in feed[:10]
            ]
        return attrs
