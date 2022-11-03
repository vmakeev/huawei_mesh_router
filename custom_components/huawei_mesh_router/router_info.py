from typing import Any


# ---------------------------
#   RouterInfo
# ---------------------------
class RouterInfo:

    def __init__(self, **kwargs: Any) -> None:
        self._serial_number = kwargs.get("serial_number")
        self._software_version = kwargs.get("software_version")
        self._hardware_version = kwargs.get("hardware_version")
        self._friendly_name = kwargs.get("friendly_name")
        self._harmony_os_version = kwargs.get("harmony_os_version")
        self._cust_device_name = kwargs.get("cust_device_name")

    @property
    def name(self) -> str:
        """Return the name of the router."""
        return self._friendly_name

    @property
    def model(self) -> str:
        """Return the model of the router."""
        return self._cust_device_name

    @property
    def serial_number(self) -> str:
        """Return the serial number of the router."""
        return self._serial_number

    @property
    def hardware_version(self) -> str:
        """Return the hardware version of the router."""
        return self._hardware_version

    @property
    def software_version(self) -> str:
        """Return the software version of the router."""
        return self._software_version

    @property
    def harmony_os_version(self) -> str:
        """Return the harmony os version of the router."""
        return self._harmony_os_version
