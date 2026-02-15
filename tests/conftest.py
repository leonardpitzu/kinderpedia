"""Shared fixtures for Kinderpedia tests."""

import pytest
from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kinderpedia.const import DOMAIN

MOCK_EMAIL = "test@example.com"
MOCK_PASSWORD = "password123"

MOCK_CONFIG_ENTRY_DATA = {
    CONF_EMAIL: MOCK_EMAIL,
    CONF_PASSWORD: MOCK_PASSWORD,
}

MOCK_CHILD = {
    "child_id": 111,
    "kindergarten_id": 222,
    "kindergarten_name": "Happy Kids",
    "avatar": "https://example.com/avatar.png",
    "first_name": "Alice",
    "last_name": "Smith",
    "birth_date": "2020-06-15",
    "gender": "f",
}

MOCK_TIMELINE_RAW = {
    "result": {
        "dailytimeline": {
            "days": {
                "2026-02-09": {
                    "data": [
                        {"id": "checkin", "subtitle": "08:15 - 16:30"},
                        {"id": "nap", "subtitle": "1 h and 30 min"},
                        {
                            "id": "food_1",
                            "details": {
                                "food": {
                                    "meals": [
                                        {
                                            "type": "md",
                                            "percent": 80,
                                            "menus": [{"name": "Cereal"}],
                                            "totals": {"kcal": 200, "weight": 150},
                                        },
                                        {
                                            "type": "mp",
                                            "percent": 90,
                                            "menus": [{"name": "Chicken soup"}],
                                            "totals": {"kcal": 400, "weight": 300},
                                        },
                                        {
                                            "type": "g",
                                            "percent": 70,
                                            "menus": [{"name": "Apple"}],
                                            "totals": {"kcal": 100, "weight": 80},
                                        },
                                    ]
                                }
                            },
                        },
                    ]
                },
                "2026-02-10": {"data": []},
                "2026-02-11": {"data": []},
                "2026-02-12": {"data": []},
                "2026-02-13": {"data": []},
            }
        }
    }
}

MOCK_CORE_RESPONSE = {
    "result": {
        "available_accounts": [
            {
                "child_id": 111,
                "kindergarten_id": 222,
                "kindergarten_name": "Happy Kids",
                "avatar": "https://example.com/avatar.png",
                "status": "active",
            }
        ],
        "children": [
            {
                "id": 111,
                "first_name": "Alice",
                "last_name": "Smith",
                "birth_date": "2020-06-15",
                "gender": "f",
            }
        ],
    }
}

MOCK_LOGIN_RESPONSE = {
    "token": "fake-jwt-token",
    "expire_at": 9999999999,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations in all tests."""
    yield


@pytest.fixture
def mock_config_entry(hass: HomeAssistant):
    """Create a mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Kinderpedia",
        data=MOCK_CONFIG_ENTRY_DATA,
        unique_id=MOCK_EMAIL,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_api():
    """Return a mocked KinderpediaAPI."""
    with patch(
        "custom_components.kinderpedia.api.KinderpediaAPI", autospec=True
    ) as mock_cls:
        api = mock_cls.return_value
        api.login = AsyncMock()
        api.fetch_children = AsyncMock(return_value=[MOCK_CHILD])
        api.fetch_timeline = AsyncMock(return_value=MOCK_TIMELINE_RAW)
        yield api
