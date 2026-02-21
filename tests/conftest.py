"""Shared fixtures for Kinderpedia tests."""

import threading

import pytest
from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kinderpedia.const import DOMAIN

# Monkey-patch threading.enumerate so the test framework's thread-leak check
# ignores the _run_safe_shutdown_loop daemon thread.  This is fixed upstream in
# pytest-homeassistant-custom-component >= 0.13.315.
_original_enumerate = threading.enumerate


def _patched_enumerate():
    return [
        t
        for t in _original_enumerate()
        if "_run_safe_shutdown_loop" not in t.name
    ]


threading.enumerate = _patched_enumerate

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
                        {"id": "nap", "subtitle": "12:39 - 14:33, 1 h and 30 min"},
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

MOCK_NEWSFEED_RAW = {
    "code": "",
    "message": "",
    "result": {
        "feed": [
            {
                "id": 37973,
                "type": "gallery",
                "user": {
                    "id": 276902,
                    "first_name": "Alina",
                    "last_name": "Vieriu",
                },
                "title": "Alina Vieriu added new photos",
                "date": "2026-02-20T15:42:42+0200",
                "date_friendly": "20 February 2026 at 15:42",
                "stats": {"likes": 8, "comments": 1, "liked": 0},
                "block_comments": False,
                "latest_comments": [
                    {
                        "id": 20856,
                        "date_friendly": "20 February 2026 at 16:52",
                        "comment": "Great photos!",
                        "sender_name": "Jane Doe",
                    }
                ],
                "allow_social_buttons": True,
                "content": {
                    "id": 40905205,
                    "type": "gallery",
                    "date": "2026-02-20T15:42:42+0200",
                    "description": "A wonderful week of activities.",
                    "title": "Holiday fun: recap, play and lots of energy!",
                    "subtitle1": "20 February 2026 at 15:42",
                    "gallery": {
                        "images": [
                            {
                                "id": 40906056,
                                "fullsize": "https://images.kinderpedia.co/photo1.jpg",
                            }
                        ],
                        "count_all": 53,
                    },
                    "video": None,
                    "file": None,
                },
                "groups": [{"id": 52118, "name": "Arici"}],
                "children": None,
            },
            {
                "id": 37736,
                "type": "invoice",
                "user": {
                    "id": 130198,
                    "first_name": "Carmen",
                    "last_name": "Boier",
                },
                "title": "Carmen Boier added a new invoice",
                "date": "2026-02-16T10:51:25+0200",
                "date_friendly": "16 February 2026 at 10:51",
                "stats": {"likes": 0, "comments": 0, "liked": 0},
                "block_comments": False,
                "latest_comments": None,
                "allow_social_buttons": False,
                "content": {
                    "id": 2061070,
                    "type": "invoice",
                    "date": "2026-02-28T00:00:00+0200",
                    "description": None,
                    "title": "Invoice number: #GH018654",
                    "subtitle1": "Due Date: 28 February 2026",
                    "subtitle2": "Total amount: 380 EUR",
                    "gallery": None,
                    "video": None,
                    "file": {
                        "src": "https://app.kinderpedia.co/invoice.pdf",
                        "size": "0 KB",
                    },
                },
                "groups": None,
                "children": None,
            },
        ]
    },
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
        api.fetch_newsfeed = AsyncMock(return_value=MOCK_NEWSFEED_RAW)
        yield api
