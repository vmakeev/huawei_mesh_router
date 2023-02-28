"""Huawei api core functions."""

import asyncio
from functools import wraps
import json
import logging
import re
from typing import Any, Callable, Dict, Final, List

import aiohttp
from aiohttp import ClientResponse
from aiohttp.abc import AbstractCookieJar
from yarl import URL

from .classes import HuaweiRsaPublicKey
from .crypto import generate_nonce, get_client_proof

TIMEOUT: Final = 5.0

SESSION_COOKIE_NAME: Final = "SessionID_R3"

APICALL_ERRCODE_UNAUTHORIZED: Final = -2
APICALL_ERRCODE_REQUEST: Final = -3

APICALL_ERRCAT_CREDENTIALS: Final = "user_pass_err"
APICALL_ERRCAT_CSRF: Final = "csrf_error"
APICALL_ERRCAT_REQUEST: Final = "request_error"
APICALL_ERRCAT_TOO_MANY_USERS: Final = "Too_Many_user"
APICALL_ERRCAT_UNAUTHORIZED: Final = "unauthorized"

AUTH_FAILURE_GENERAL: Final = "auth_general"
AUTH_FAILURE_CREDENTIALS: Final = "auth_invalid_credentials"
AUTH_FAILURE_CSRF: Final = "auth_invalid_csrf"
AUTH_FAILURE_TOO_MANY_USERS: Final = "auth_too_many_users"


# ---------------------------
#   AuthenticationError
# ---------------------------
class AuthenticationError(Exception):
    def __init__(self, message: str, reason_code: str) -> None:
        """Initialize."""
        super().__init__(message)
        self._message = message
        self._reason_code = reason_code

    @property
    def reason_code(self) -> str | None:
        """Error reason code."""
        return self._reason_code

    def __str__(self, *args, **kwargs) -> str:
        """Return str(self)."""
        return f"{self._message}; reason: {self._reason_code}"

    def __repr__(self) -> str:
        """Return repr(self)."""
        return self.__str__()


# ---------------------------
#   ApiCallError
# ---------------------------
class ApiCallError(Exception):
    def __init__(
        self, message: str, error_code: int | None, error_category: str | None
    ):
        """Initialize."""
        super().__init__(message)
        self._message = message
        self._error_code = error_code
        self._error_category = error_category

    @property
    def code(self) -> int | None:
        """Error code."""
        return self._error_code

    @property
    def category(self) -> int | None:
        """Error category."""
        return self._error_category

    def __str__(self, *args, **kwargs) -> str:
        """Return str(self)."""
        return f"{self._message}; code: {self._error_code}, category: {self._error_category}"

    def __repr__(self) -> str:
        """Return repr(self)."""
        return self.__str__()


# ---------------------------
#   handle_auth_exception
# ---------------------------
def handle_auth_exception(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        logger = args[0]._logger
        try:
            return await func(*args, **kwargs)
        except ApiCallError as ex:
            if ex.category == APICALL_ERRCAT_CREDENTIALS:
                raise AuthenticationError(
                    "Invalid username or password", AUTH_FAILURE_CREDENTIALS
                )
            if ex.category == APICALL_ERRCAT_CSRF:
                raise AuthenticationError("CSRF error, try again", AUTH_FAILURE_CSRF)

            if ex.category == APICALL_ERRCAT_TOO_MANY_USERS:
                raise AuthenticationError(
                    "Too many users, wait some time before retry",
                    AUTH_FAILURE_TOO_MANY_USERS,
                )

            logger.debug("Authentication failed: %s", {repr(ex)})
            raise AuthenticationError(
                "Authentication failed due to api call error", AUTH_FAILURE_GENERAL
            )
        except AuthenticationError:
            raise
        except Exception as ex:
            logger.debug("Authentication failed: %s", {repr(ex)})
            raise AuthenticationError(
                "Authentication failed due to unknown error", AUTH_FAILURE_GENERAL
            )

    return wrapper


# ---------------------------
#   retry_on_csrf_error
# ---------------------------
def retry_on_csrf_error(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        api = args[0]
        logger = api._logger
        try:
            return await func(*args, **kwargs)
        except ApiCallError as ex:
            if ex.category == APICALL_ERRCAT_CSRF:
                logger.debug("CSRF error detected, retry")
                if await api._init_csrf():
                    return await func(*args, **kwargs)
            raise

    return wrapper


# ---------------------------
#   lock_external_call
# ---------------------------
def lock_external_call(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        api: HuaweiCoreApi = args[0]
        async with api._call_locker:
            return await func(*args, **kwargs)

    return wrapper


# ---------------------------
#   lock_auth_call
# ---------------------------
def lock_auth_call(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        api: HuaweiCoreApi = args[0]
        async with api._auth_locker:
            return await func(*args, **kwargs)

    return wrapper


# ---------------------------
#   _get_response_text
# ---------------------------
async def _get_response_text(response: ClientResponse) -> str:
    content_bytes = await response.content.read()
    text = content_bytes.decode("utf-8")
    return text


# ---------------------------
#   _get_response_json
# ---------------------------
async def _get_response_json(response: ClientResponse) -> Dict | None:
    text = await _get_response_text(response)
    return json.loads(text) if text else None


# ---------------------------
#   _check_authorized
# ---------------------------
def _check_authorized(response: ClientResponse, result: Dict) -> bool:
    return response.status != 404


# ---------------------------
#   HuaweiCoreApi
# ---------------------------
class HuaweiCoreApi:
    def __init__(
        self,
        host: str,
        port: int,
        use_ssl: bool,
        user: str,
        password: str,
        verify_ssl: bool,
    ) -> None:
        """Initialize."""
        self._logger = logging.getLogger(f"{__name__} ({host})")
        self._logger.debug("New instance of HuaweiCoreApi created")
        self._user: str = user
        self._password: str = password
        self._verify_ssl: bool = verify_ssl
        self._session: aiohttp.ClientSession | None = None
        self._active_csrf: Dict | None = None
        self._public_key: Dict | None = None
        self._is_initialized: bool = False
        self._call_locker = asyncio.Lock()
        self._auth_locker = asyncio.Lock()

        schema = "https" if use_ssl else "http"
        self._base_url: str = f"{schema}://{host}:{port}"

    @property
    def router_url(self) -> str:
        """Return router's configuration url."""
        return self._get_url("html/index.html")

    @property
    def rsa_key(self) -> HuaweiRsaPublicKey | None:
        if self._public_key is None:
            return None
        return HuaweiRsaPublicKey(
            rsan=self._public_key["rsan"],
            rsae=self._public_key["rsae"],
            signature=self._public_key["rsapubkeysignature"],
        )

    def _handle_error_dict(self, data: Dict | None) -> None:
        """handle dict with errors"""
        if data is None:
            return

        if "err" in data and data["err"] != 0:
            error_code = data["err"]
            error_category = data.get("errorCategory", "unknown")
            self._logger.debug("Error data detected in the response. %s", data)
            raise ApiCallError(
                "Api call returns unsuccessful result", error_code, error_category
            )

        if "errcode" in data and data["errcode"] != 0:
            error_code = data["errcode"]
            error_category = (
                APICALL_ERRCAT_CSRF if data.get("csrf") == "Menu.csrf_err" else None
            )
            self._logger.debug("Error code detected in the response. %s", data)
            raise ApiCallError(
                "Api call returns unsuccessful result", error_code, error_category
            )

    def _check_has_cookies(self, cookie_jar: AbstractCookieJar, url: URL) -> None:
        """check cookies"""
        host_cookies = cookie_jar.filter_cookies(url)
        if not host_cookies.get(SESSION_COOKIE_NAME):
            self._logger.warning("Session cookies not found, url is '%s'.", url)
        else:
            self._logger.debug("Session cookies stored")

    def _get_url(self, path) -> str:
        """Return full address to the endpoint."""
        return self._base_url + "/" + path

    def _update_csrf(self, csrf_param: str, csrf_token: str) -> None:
        """Update the csrf parameters that needed to make the next request."""
        self._active_csrf = {"csrf_param": csrf_param, "csrf_token": csrf_token}
        self._logger.debug(
            "Csrf updated: param is '%s', token is '%s'", csrf_param, csrf_token
        )

    def _handle_csrf_dict(self, data: Dict | None) -> None:
        """Process the response dict and update csrf parameters if they exist in the response."""
        if data is not None and "csrf_param" in data and "csrf_token" in data:
            self._update_csrf(data["csrf_param"], data["csrf_token"])
        else:
            self._logger.debug("No csrf data found in the response")

    def _handle_public_key_dict(self, data: Dict | None) -> None:
        """Process the response dict and update the public key if it exists in the response"""
        if (
            data is not None
            and "rsan" in data
            and "rsae" in data
            and "rsapubkeysignature" in data
        ):
            self._public_key = {
                "rsan": data["rsan"],
                "rsae": data["rsae"],
                "rsapubkeysignature": data["rsapubkeysignature"],
            }
            self._logger.debug("Public key updated")
        else:
            self._logger.warning("No public key found in the response")
            self._public_key = None

    async def _ensure_initialized(self) -> None:
        """Ensure that initial authorization was completed successfully."""
        if not self._is_initialized:
            await self.authenticate()
            self._is_initialized = True

    async def _get_raw(self, path: str) -> ClientResponse:
        """Perform GET request to the specified relative URL and return raw ClientResponse."""
        try:
            self._logger.debug("Performing GET to %s", path)
            response = await self._session.get(
                url=self._get_url(path),
                allow_redirects=True,
                verify_ssl=self._verify_ssl,
                timeout=TIMEOUT,
            )
            self._logger.debug("GET %s performed, status: %s", path, response.status)
            return response
        except Exception as ex:
            self._logger.debug("GET %s failed: %s", path, str(ex))
            raise ApiCallError(
                f"Can not perform GET request at {path} cause of {repr(ex)}",
                APICALL_ERRCODE_REQUEST,
                APICALL_ERRCAT_REQUEST,
            )

    async def _post_raw(
        self, path: str, data: Dict, headers: dict = None
    ) -> ClientResponse:
        """Perform POST request to the specified relative URL with specified body and return raw ClientResponse."""
        try:
            self._logger.debug("Performing POST to %s", path)
            response = await self._session.post(
                url=self._get_url(path),
                data=json.dumps(data),
                verify_ssl=self._verify_ssl,
                timeout=TIMEOUT,
                headers=headers,
            )
            self._logger.debug(
                "POST to %s performed, status: %s", path, response.status
            )
            return response
        except Exception as ex:
            self._logger.debug("POST %s failed: %s", path, str(ex))
            raise ApiCallError(
                f"Can not perform POST request at {path} cause of {repr(ex)}",
                APICALL_ERRCODE_REQUEST,
                APICALL_ERRCAT_REQUEST,
            )

    def _refresh_session(self) -> None:
        """Initialize the client session (if not exists) and clear cookies."""
        self._logger.debug("Refresh session called")
        if self._session is None:
            """Unsafe cookies for IP addresses instead of domain names"""
            jar = aiohttp.CookieJar(unsafe=True)
            self._session = aiohttp.ClientSession(cookie_jar=jar)
            self._logger.debug("Session created")
        self._session.cookie_jar.clear()
        self._active_csrf = None

    @handle_auth_exception
    @lock_auth_call
    async def authenticate(self) -> None:
        """Perform authentication and return true when authentication success"""
        self._logger.debug("Authentication started")
        self._refresh_session()
        self._logger.debug("Getting index")

        if not await self._init_csrf():
            raise AuthenticationError(
                "Failed to get initial CSRF", AUTH_FAILURE_GENERAL
            )

        self._check_has_cookies(self._session.cookie_jar, URL(self._base_url))

        first_nonce = generate_nonce()

        self._logger.debug("Sending nonce")
        response = await self._post_raw(
            "api/system/user_login_nonce",
            {
                "csrf": self._active_csrf,
                "data": {"username": self._user, "firstnonce": first_nonce},
            },
        )
        if response.status != 200:
            self._logger.debug(
                "Authentication failed: can not send nonce, status is %s",
                response.status,
            )
            raise AuthenticationError("Failed to send nonce", AUTH_FAILURE_GENERAL)

        result = await _get_response_json(response)
        self._handle_csrf_dict(result)
        self._handle_error_dict(result)

        server_nonce = result["servernonce"]
        iterations = int(result["iterations"])
        salt = result["salt"]

        client_proof = get_client_proof(
            self._password, salt, iterations, first_nonce, server_nonce
        )

        self._logger.debug("Sending proof")
        response = await self._post_raw(
            "api/system/user_login_proof",
            {
                "csrf": self._active_csrf,
                "data": {
                    "clientproof": client_proof,
                    "finalnonce": server_nonce,
                },
            },
        )
        if response.status != 200:
            self._logger.debug(
                "Authentication failed: can not send proof, status is %s",
                response.status,
            )
            raise AuthenticationError("Failed to send proof", AUTH_FAILURE_GENERAL)

        result = await _get_response_json(response)
        self._handle_csrf_dict(result)
        self._handle_error_dict(result)
        self._handle_public_key_dict(result)

        self._logger.debug("Authentication success")

    async def _init_csrf(self) -> bool:
        response = await self._get_raw("html/index.html#/login")
        if response.status != 200:
            self._logger.debug(
                "Can not get index, status is %s",
                response.status,
            )
            return False
        result = await _get_response_text(response)
        csrf_param = re.search(
            '<meta name="csrf_param" content="(.+)"/>', result
        ).group(1)
        csrf_token = re.search(
            '<meta name="csrf_token" content="(.+)"/>', result
        ).group(1)
        self._update_csrf(csrf_param, csrf_token)
        return True

    @retry_on_csrf_error
    async def _try_logout(self):
        """Try logout from the api"""
        try:
            response = await self._post_raw(
                "api/system/user_logout", {"csrf": self._active_csrf}
            )

            if response.status != 200:
                self._logger.debug(
                    "Can not perform logout: status is %s", response.status
                )
                return

            result = await _get_response_json(response)
            self._handle_csrf_dict(result)
            self._handle_error_dict(result)
        except Exception as ex:
            self._logger.debug("Error during logout: %s", repr(ex))

    @retry_on_csrf_error
    @lock_external_call
    async def get(self, path: str, **kwargs: Any) -> Dict | List:
        """Perform GET request to the relative address."""
        await self._ensure_initialized()

        check_authorized: Callable[[ClientResponse, Dict], bool] = (
            kwargs.get("check_authorized") or _check_authorized
        )

        response = await self._get_raw(path)
        result = await _get_response_json(response)

        if not check_authorized(response, result):
            self._logger.debug("GET seems unauthorized, trying to re-authenticate")
            await self._try_logout()
            await self.authenticate()
            response = await self._get_raw(path)
            result = await _get_response_json(response)

            if not check_authorized(response, result):
                raise ApiCallError(
                    f"Api call error, status:{response.status}",
                    APICALL_ERRCODE_UNAUTHORIZED,
                    APICALL_ERRCAT_UNAUTHORIZED,
                )

        self._handle_csrf_dict(result)
        self._handle_error_dict(result)
        return result

    @retry_on_csrf_error
    @lock_external_call
    async def post(self, path: str, payload: Dict, **kwargs: Any) -> Dict:
        """Perform POST request to the relative address with the specified body."""
        await self._ensure_initialized()

        check_authorized: Callable[[ClientResponse, Dict | None], bool] = (
            kwargs.get("check_authorized") or _check_authorized
        )

        dto = {"data": payload, "csrf": self._active_csrf}
        if kwargs.get("extra_data") is not None:
            for key, value in kwargs.get("extra_data", {}).items():
                dto[key] = value

        headers = kwargs.get("headers")

        response = await self._post_raw(path, dto, headers=headers)
        result = await _get_response_json(response)

        self._handle_csrf_dict(result)
        self._handle_error_dict(result)

        if not check_authorized(response, result):
            self._logger.debug("POST seems unauthorized, trying to re-authenticate")
            await self._try_logout()
            await self.authenticate()

            dto = {"csrf": self._active_csrf, "data": payload}
            if kwargs.get("extra_data") is not None:
                for key, value in kwargs.get("extra_data", {}).items():
                    dto[key] = value

            response = await self._post_raw(path, dto, headers=headers)
            result = await _get_response_json(response)
            if not check_authorized(response, result):
                raise ApiCallError(
                    f"Api call error, status:{response.status}",
                    APICALL_ERRCODE_UNAUTHORIZED,
                    APICALL_ERRCAT_UNAUTHORIZED,
                )

            self._handle_csrf_dict(result)
            self._handle_error_dict(result)

        return result

    @lock_external_call
    @lock_auth_call
    async def disconnect(self) -> None:
        """Close session."""
        self._logger.debug("Disconnecting")
        if self._session is not None:
            await self._try_logout()
            await self._session.close()
            self._session = None
