"""Tests for the Kinderpedia config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResultType

from custom_components.kinderpedia.const import DOMAIN
from custom_components.kinderpedia.api import KinderpediaAuthError, KinderpediaConnectionError

from tests.conftest import MOCK_EMAIL, MOCK_PASSWORD, MOCK_CHILD


async def test_user_form_shown(hass: HomeAssistant):
    """Test that the user form is shown on first step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_successful_config_flow(hass: HomeAssistant):
    """Test a successful config flow creates an entry."""
    with patch(
        "custom_components.kinderpedia.config_flow.KinderpediaAPI"
    ) as mock_api_cls:
        mock_api = mock_api_cls.return_value
        mock_api.fetch_children = AsyncMock(return_value=[MOCK_CHILD])

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Kinderpedia"
    assert result["data"][CONF_EMAIL] == MOCK_EMAIL
    assert result["data"][CONF_PASSWORD] == MOCK_PASSWORD


async def test_auth_error(hass: HomeAssistant):
    """Test config flow handles authentication errors."""
    with patch(
        "custom_components.kinderpedia.config_flow.KinderpediaAPI"
    ) as mock_api_cls:
        mock_api = mock_api_cls.return_value
        mock_api.fetch_children = AsyncMock(side_effect=KinderpediaAuthError("bad creds"))

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_connection_error(hass: HomeAssistant):
    """Test config flow handles connection errors."""
    with patch(
        "custom_components.kinderpedia.config_flow.KinderpediaAPI"
    ) as mock_api_cls:
        mock_api = mock_api_cls.return_value
        mock_api.fetch_children = AsyncMock(
            side_effect=KinderpediaConnectionError("timeout")
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_generic_exception(hass: HomeAssistant):
    """Test config flow handles unexpected exceptions."""
    with patch(
        "custom_components.kinderpedia.config_flow.KinderpediaAPI"
    ) as mock_api_cls:
        mock_api = mock_api_cls.return_value
        mock_api.fetch_children = AsyncMock(side_effect=RuntimeError("boom"))

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_no_children_found(hass: HomeAssistant):
    """Test config flow handles no children being discovered."""
    with patch(
        "custom_components.kinderpedia.config_flow.KinderpediaAPI"
    ) as mock_api_cls:
        mock_api = mock_api_cls.return_value
        mock_api.fetch_children = AsyncMock(return_value=[])

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "no_children_found"}


async def test_duplicate_entry(hass: HomeAssistant, mock_config_entry):
    """Test config flow aborts when account is already configured."""
    with patch(
        "custom_components.kinderpedia.config_flow.KinderpediaAPI"
    ) as mock_api_cls:
        mock_api = mock_api_cls.return_value
        mock_api.fetch_children = AsyncMock(return_value=[MOCK_CHILD])

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
