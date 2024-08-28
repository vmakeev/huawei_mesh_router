"""Config flow to configure Huawei Mesh Router."""

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, FlowResult, OptionsFlow
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback

from .client.coreapi import AuthenticationError
from .client.huaweiapi import HuaweiApi
from .const import (
    DEFAULT_DEVICE_TRACKER,
    DEFAULT_DEVICE_TRACKER_ZONES,
    DEFAULT_DEVICES_TAGS,
    DEFAULT_EVENT_ENTITIES,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PASS,
    DEFAULT_PORT,
    DEFAULT_PORT_MAPPING_SWITCHES,
    DEFAULT_ROUTER_CLIENTS_SENSORS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SSL,
    DEFAULT_TIME_CONTROL_SWITCHES,
    DEFAULT_URL_FILTER_SWITCHES,
    DEFAULT_USER,
    DEFAULT_VERIFY_SSL,
    DEFAULT_WIFI_ACCESS_SWITCHES,
    DOMAIN,
    OPT_DEVICE_TRACKER,
    OPT_DEVICE_TRACKER_ZONES,
    OPT_DEVICES_TAGS,
    OPT_EVENT_ENTITIES,
    OPT_PORT_MAPPING_SWITCHES,
    OPT_ROUTER_CLIENTS_SENSORS,
    OPT_TIME_CONTROL_SWITCHES,
    OPT_URL_FILTER_SWITCHES,
    OPT_WIFI_ACCESS_SWITCHES,
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

    VERSION = 6

    def __init__(self):
        """Initialize HuaweiControllerConfigFlow."""

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return HuaweiControllerOptionsFlowHandler(config_entry)

    async def async_step_import(self, user_input=None) -> FlowResult:
        """Occurs when a previously entry setup fails and is re-initiated."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None) -> FlowResult:
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
    def _show_config_form(self, user_input, errors=None) -> FlowResult:
        """Show the configuration form to edit data."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=user_input[CONF_NAME]): str,
                    vol.Required(CONF_HOST, default=user_input[CONF_HOST]): str,
                    vol.Required(CONF_USERNAME, default=user_input[CONF_USERNAME]): str,
                    vol.Required(CONF_PASSWORD, default=user_input[CONF_PASSWORD]): str,
                    vol.Required(CONF_PORT, default=user_input[CONF_PORT]): int,
                    vol.Required(CONF_SSL, default=user_input[CONF_SSL]): bool,
                    vol.Required(
                        CONF_VERIFY_SSL, default=user_input[CONF_VERIFY_SSL]
                    ): bool,
                }
            ),
            errors=errors,
        )


# ---------------------------
#   HuaweiControllerOptionsFlowHandler
# ---------------------------
class HuaweiControllerOptionsFlowHandler(OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Manage the options."""
        return await self.async_step_basic_options(user_input)

    async def async_step_basic_options(self, user_input=None) -> FlowResult:
        """Manage the basic options."""
        if user_input is not None:
            self.options.update(user_input)
            return await self.async_step_features_select()

        return self.async_show_form(
            step_id="basic_options",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL,
                            self.config_entry.data.get(
                                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                            ),
                        ),
                    ): int,
                }
            ),
        )

    async def async_step_features_select(self, user_input=None) -> FlowResult:
        """Manage the features select options."""
        if user_input is not None:
            self.options.update(user_input)
            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="features_select",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        OPT_WIFI_ACCESS_SWITCHES,
                        default=self.options.get(
                            OPT_WIFI_ACCESS_SWITCHES, DEFAULT_WIFI_ACCESS_SWITCHES
                        ),
                    ): bool,
                    vol.Required(
                        OPT_ROUTER_CLIENTS_SENSORS,
                        default=self.options.get(
                            OPT_ROUTER_CLIENTS_SENSORS, DEFAULT_ROUTER_CLIENTS_SENSORS
                        ),
                    ): bool,
                    vol.Required(
                        OPT_DEVICES_TAGS,
                        default=self.options.get(
                            OPT_DEVICES_TAGS, DEFAULT_DEVICES_TAGS
                        ),
                    ): bool,
                    vol.Required(
                        OPT_DEVICE_TRACKER,
                        default=self.options.get(
                            OPT_DEVICE_TRACKER, DEFAULT_DEVICE_TRACKER
                        ),
                    ): bool,
                    vol.Required(
                        OPT_DEVICE_TRACKER_ZONES,
                        default=self.options.get(
                            OPT_DEVICE_TRACKER_ZONES, DEFAULT_DEVICE_TRACKER_ZONES
                        ),
                    ): bool,
                    vol.Required(
                        OPT_URL_FILTER_SWITCHES,
                        default=self.options.get(
                            OPT_URL_FILTER_SWITCHES, DEFAULT_URL_FILTER_SWITCHES
                        ),
                    ): bool,
                    vol.Required(
                        OPT_EVENT_ENTITIES,
                        default=self.options.get(
                            OPT_EVENT_ENTITIES, DEFAULT_EVENT_ENTITIES
                        ),
                    ): bool,
                    vol.Required(
                        OPT_PORT_MAPPING_SWITCHES,
                        default=self.options.get(
                            OPT_PORT_MAPPING_SWITCHES, DEFAULT_PORT_MAPPING_SWITCHES
                        ),
                    ): bool,
                    vol.Required(
                        OPT_TIME_CONTROL_SWITCHES,
                        default=self.options.get(
                            OPT_TIME_CONTROL_SWITCHES, DEFAULT_TIME_CONTROL_SWITCHES
                        ),
                    ): bool,
                },
            ),
        )
