"""Diagnostics support for Kinderpedia."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT_CONFIG = {CONF_EMAIL, CONF_PASSWORD}
TO_REDACT_DATA = {"avatar", "first_name", "last_name", "birth_date"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    return {
        "config_entry": async_redact_data(dict(entry.data), TO_REDACT_CONFIG),
        "coordinator_data": _redact_coordinator_data(coordinator.data),
    }


def _redact_coordinator_data(data: dict | None) -> dict:
    """Deep-redact sensitive fields from coordinator data."""
    if not data:
        return {}

    redacted = {"last_updated": data.get("last_updated")}
    children = {}

    for key, child_data in data.get("children", {}).items():
        child_info = child_data.get("child", {})
        children[key] = {
            "child": async_redact_data(dict(child_info), TO_REDACT_DATA),
            "days": child_data.get("days", {}),
        }

    redacted["children"] = children
    return redacted
