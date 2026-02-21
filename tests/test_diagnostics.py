"""Tests for Kinderpedia diagnostics."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from custom_components.kinderpedia.const import DOMAIN
from custom_components.kinderpedia.diagnostics import (
    async_get_config_entry_diagnostics,
)
from tests.conftest import MOCK_CHILD, MOCK_TIMELINE_RAW


async def test_diagnostics_redacts_credentials(
    hass: HomeAssistant, mock_config_entry
):
    """Config entry email/password must be redacted."""
    coordinator = MagicMock()
    coordinator.data = None

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][mock_config_entry.entry_id] = {"coordinator": coordinator}

    diag = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert diag["config_entry"]["email"] == "**REDACTED**"
    assert diag["config_entry"]["password"] == "**REDACTED**"


async def test_diagnostics_redacts_child_pii(
    hass: HomeAssistant, mock_config_entry
):
    """Sensitive child fields must be redacted."""
    from custom_components.kinderpedia.coordinator import _parse_timeline

    parsed_days = _parse_timeline(MOCK_TIMELINE_RAW)

    coordinator = MagicMock()
    coordinator.data = {
        "last_updated": "2026-02-21 12:00:00",
        "children": {
            "111_222": {
                "child": dict(MOCK_CHILD),
                "days": parsed_days,
            }
        },
    }

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][mock_config_entry.entry_id] = {"coordinator": coordinator}

    diag = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    child_diag = diag["coordinator_data"]["children"]["111_222"]["child"]

    assert child_diag["first_name"] == "**REDACTED**"
    assert child_diag["last_name"] == "**REDACTED**"
    assert child_diag["birth_date"] == "**REDACTED**"
    assert child_diag["avatar"] == "**REDACTED**"

    # Non-sensitive fields should still be present
    assert child_diag["child_id"] == 111
    assert child_diag["kindergarten_id"] == 222


async def test_diagnostics_includes_day_data(
    hass: HomeAssistant, mock_config_entry
):
    """Day data must be included unredacted for troubleshooting."""
    from custom_components.kinderpedia.coordinator import _parse_timeline

    parsed_days = _parse_timeline(MOCK_TIMELINE_RAW)

    coordinator = MagicMock()
    coordinator.data = {
        "last_updated": "2026-02-21 12:00:00",
        "children": {
            "111_222": {
                "child": dict(MOCK_CHILD),
                "days": parsed_days,
            }
        },
    }

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][mock_config_entry.entry_id] = {"coordinator": coordinator}

    diag = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    days = diag["coordinator_data"]["children"]["111_222"]["days"]

    assert "monday" in days
    assert days["monday"]["checkin"] == "08:15 - 16:30"


async def test_diagnostics_empty_coordinator_data(
    hass: HomeAssistant, mock_config_entry
):
    """Handle coordinator returning None gracefully."""
    coordinator = MagicMock()
    coordinator.data = None

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][mock_config_entry.entry_id] = {"coordinator": coordinator}

    diag = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert diag["coordinator_data"] == {}
