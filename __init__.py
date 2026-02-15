import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, PLATFORMS
from .api import KinderpediaAPI, KinderpediaAuthError, KinderpediaConnectionError
from .coordinator import KinderpediaDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data.setdefault(DOMAIN, {})

    email = entry.data["email"]
    password = entry.data["password"]

    api = KinderpediaAPI(hass, email, password)

    try:
        await api.login()
    except KinderpediaConnectionError as err:
        raise ConfigEntryNotReady(f"Cannot connect to Kinderpedia: {err}") from err
    except KinderpediaAuthError as err:
        _LOGGER.error("Kinderpedia authentication failed: %s", err)
        return False

    coordinator = KinderpediaDataUpdateCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
