"""Config flow to configure Huawei Mesh Router."""

import logging

import voluptuous as vol
from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_POLL,
    ConfigFlow
)
from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_VERIFY_SSL,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import callback
from .client.coreapi import AuthenticationError
from .client.huaweiapi import HuaweiApi

from .const import (
    DOMAIN,
    DEFAULT_HOST,
    DEFAULT_USER,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_PASS,
    DEFAULT_NAME,
    DEFAULT_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


# ---------------------------
#   configured_instances
# ---------------------------
@callback
def configured_instances(hass):
    """Return a set of configured instances."""
    return set(
        entry.data[CONF_NAME] for entry in hass.config_entries.async_entries(DOMAIN)
    )


# ---------------------------
#   HuaweiControllerConfigFlow
# ---------------------------
class HuaweiControllerConfigFlow(ConfigFlow, domain=DOMAIN):
    """HuaweiControllerConfigFlow class"""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize HuaweiControllerConfigFlow."""

    async def async_step_import(self, user_input=None):
        """Occurs when a previously entry setup fails and is re-initiated."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            # Check if instance with this name already exists
            if user_input[CONF_NAME] in configured_instances(self.hass):
                errors["base"] = "name_exists"

            # Test connection
            api = HuaweiApi(
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
                use_ssl=user_input[CONF_SSL],
                user=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                verify_ssl=user_input[CONF_VERIFY_SSL],
            )
            try:
                await api.authenticate()
            except AuthenticationError as aex:
                errors["base"] = aex.reason_code or "auth_general"
            except Exception as ex:
                _LOGGER.warning("Setup failed: %s", {str(ex)})
                errors["base"] = "auth_general"
            finally:
                await api.disconnect()

            # Save instance
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

            return self._show_config_form(user_input=user_input, errors=errors)

        return self._show_config_form(
            user_input={
                CONF_NAME: DEFAULT_NAME,
                CONF_HOST: DEFAULT_HOST,
                CONF_USERNAME: DEFAULT_USER,
                CONF_PASSWORD: DEFAULT_PASS,
                CONF_PORT: DEFAULT_PORT,
                CONF_SSL: DEFAULT_SSL,
                CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
                CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            },
            errors=errors,
        )

    # ---------------------------
    #   _show_config_form
    # ---------------------------
    def _show_config_form(self, user_input, errors=None):
        """Show the configuration form to edit data."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=user_input[CONF_NAME]): str,
                    vol.Required(CONF_HOST, default=user_input[CONF_HOST]): str,
                    vol.Required(CONF_USERNAME, default=user_input[CONF_USERNAME]): str,
                    vol.Required(CONF_PASSWORD, default=user_input[CONF_PASSWORD]): str,
                    vol.Optional(CONF_PORT, default=user_input[CONF_PORT]): int,
                    vol.Optional(CONF_SSL, default=user_input[CONF_SSL]): bool,
                    vol.Optional(CONF_VERIFY_SSL, default=user_input[CONF_VERIFY_SSL]): bool,
                    vol.Optional(CONF_SCAN_INTERVAL, default=user_input[CONF_SCAN_INTERVAL]): int,
                }
            ),
            errors=errors,
        )