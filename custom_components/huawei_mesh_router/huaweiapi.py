import json
import logging
import hmac
import hashlib
import asyncio
from typing import Dict, Any

import aiohttp
import re

from random import randbytes
from aiohttp import ClientResponse

TIMEOUT = 5.0
_LOGGER = logging.getLogger(__name__)

AUTH_FAILURE_GENERAL = "auth_general"
AUTH_FAILURE_CREDENTIALS = "auth_invalid_credentials"


class AuthenticationError(Exception):

    def __init__(self, message: str, reason_code: str):
        super().__init__(message)
        self._message = message
        self._reason_code = reason_code

    @property
    def reason_code(self) -> str | None:
        return self._reason_code

    def __str__(self, *args, **kwargs):
        """ Return str(self). """
        return f"{self._message}; reason: {self._reason_code}"


class ApiCallError(Exception):

    def __init__(self, message: str, error_code: int | None, error_category: str | None):
        super().__init__(message)
        self._message = message
        self._error_code = error_code
        self._error_category = error_category

    @property
    def code(self) -> int | None:
        return self._error_code

    @property
    def category(self) -> int | None:
        return self._error_category

    def __str__(self, *args, **kwargs):
        """ Return str(self). """
        return f"{self._message}; code: {self._error_code}, category: {self._error_category}"


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
async def _get_response_json(response: ClientResponse) -> Dict:
    text = await _get_response_text(response)
    result = json.loads(text)
    return result


# ---------------------------
#   _handle_error_dict
# ---------------------------
def _handle_error_dict(data: Dict) -> None:
    if "err" in data and data["err"] != 0:
        error_code = data["err"]
        error_category = data.get("errorCategory", "unknown")
        _LOGGER.debug("Error data detected in the response: %s %s", error_code, error_category)
        _LOGGER.debug("Response body with err: %s", data)
        raise ApiCallError("Api call returns unsuccessful result", error_code, error_category)

    if "errcode" in data and data["errcode"] != 0:
        error_code = data["errcode"]
        error_category = "csrf_error" if data.get('csrf') == "Menu.csrf_err" else None
        _LOGGER.debug("Error code detected in the response: %s %s", error_code, error_category)
        _LOGGER.debug("Response body with errcode: %s", data)
        raise ApiCallError("Api call returns unsuccessful result", error_code, error_category)


# ---------------------------
#   _check_authorized
# ---------------------------
def _check_authorized(response: ClientResponse, result: Dict):
    return response.status != 404


# ---------------------------
#   HuaweiApi
# ---------------------------
class HuaweiApi:

    def __init__(
            self,
            host: str,
            port: int,
            use_ssl: bool,
            user: str,
            password: str,
            verify_ssl: bool
    ) -> None:
        _LOGGER.debug("New instance of HuaweiApi created")
        self._user: str = user
        self._password: str = password
        self._verify_ssl: bool = verify_ssl
        self._session: aiohttp.ClientSession | None = None
        self._active_csrf: Dict | None = None
        self._is_initialized: bool = False
        self._call_locker = asyncio.Lock()

        schema = "https" if use_ssl else "http"
        self._base_url: str = "{0}://{1}:{2}".format(schema, host, port)

    @property
    def router_url(self) -> str:
        """Return router"s configuration url."""
        return self._get_url("html/index.html")

    def _get_url(self, path) -> str:
        """Return full address to the endpoint."""
        return self._base_url + "/" + path

    def _update_csrf(self, csrf_param: str, csrf_token: str) -> None:
        """Update the csrf parameters that needed to make the next request."""
        self._active_csrf = {"csrf_param": csrf_param, "csrf_token": csrf_token}
        _LOGGER.debug("Csrf updated: param is '%s', token is '%s'", csrf_param, csrf_token)

    def _handle_csrf_dict(self, data: Dict) -> None:
        """Process the response dict and update csrf parameters if they exist in the response."""
        if "csrf_param" in data and "csrf_token" in data:
            self._update_csrf(data["csrf_param"], data['csrf_token'])
        else:
            _LOGGER.debug("No csrf data found in the response")

    async def _ensure_initialized(self) -> None:
        """Ensure that initial authorization was completed successfully."""
        if not self._is_initialized:
            await self.authenticate()
            self._is_initialized = True

    async def _get_raw(self, path: str) -> ClientResponse:
        """Perform GET request to the specified relative URL and return raw ClientResponse."""
        try:
            _LOGGER.debug("Cookies before GET: %s", self._session.cookie_jar._cookies)
            _LOGGER.debug("Performing GET to %s", path)
            response = await self._session.get(url=self._get_url(path),
                                               allow_redirects=True,
                                               verify_ssl=self._verify_ssl,
                                               timeout=TIMEOUT)
            _LOGGER.debug("GET %s performed, status: %s", path, response.status)
            _LOGGER.debug("Cookies after GET: %s", self._session.cookie_jar._cookies)
            return response
        except Exception as ex:
            _LOGGER.error("GET %s failed: %s", path, str(ex))
            raise ApiCallError(f"Can not perform GET request at {path} cause of {str(ex)}", None, "request_error")

    async def _post_raw(self, path: str, data: Dict) -> ClientResponse:
        """Perform POST request to the specified relative URL with specified body and return raw ClientResponse."""
        try:
            _LOGGER.debug("Cookies before POST: %s", self._session.cookie_jar._cookies)
            _LOGGER.debug('Performing POST to %s', path)
            _LOGGER.debug('POST body: %s', json.dumps(data))
            response = await self._session.post(url=self._get_url(path),
                                                data=json.dumps(data),
                                                verify_ssl=self._verify_ssl,
                                                timeout=TIMEOUT)
            _LOGGER.debug('POST to %s performed, status: %s', path, response.status)
            _LOGGER.debug("Cookies after POST: %s", self._session.cookie_jar._cookies)
            return response
        except Exception as ex:
            _LOGGER.error("POST %s failed: %s", path, str(ex))
            raise ApiCallError(f'Can not perform POST request at {path} cause of {str(ex)}', None, "request_error")

    def _refresh_session(self) -> None:
        """Initialize the client session (if not exists) and clear cookies."""
        _LOGGER.debug("Refresh session called")
        if self._session is None:
            jar = aiohttp.CookieJar(unsafe=True)
            self._session = aiohttp.ClientSession(cookie_jar=jar)
            _LOGGER.debug("Session created")
        self._session.cookie_jar.clear()
        self._active_csrf = None

    async def authenticate(self) -> None:
        """Perform authentication and return true when authentication success"""
        try:
            _LOGGER.debug("Authentication started")
            self._refresh_session()
            _LOGGER.debug("Getting index")
            response = await self._get_raw("html/index.html#/login")

            if response.status != 200:
                _LOGGER.error("Authentication failed: can not get index, status is %s", response.status)
                raise AuthenticationError("Failed to get index", AUTH_FAILURE_GENERAL)

            result = await _get_response_text(response)

            csrf_param = re.search('<meta name="csrf_param" content="(.+)"/>', result).group(1)
            csrf_token = re.search('<meta name="csrf_token" content="(.+)"/>', result).group(1)
            self._update_csrf(csrf_param, csrf_token)

            first_nonce = randbytes(32).hex()

            _LOGGER.debug("Sending nonce")
            response = await self._post_raw("api/system/user_login_nonce",
                                            {"csrf": self._active_csrf,
                                             "data": {"username": self._user, "firstnonce": first_nonce}})
            if response.status != 200:
                _LOGGER.error("Authentication failed: can not send nonce, status is %s", response.status)
                raise AuthenticationError("Failed to send nonce", AUTH_FAILURE_GENERAL)

            result = await _get_response_json(response)
            self._handle_csrf_dict(result)
            _handle_error_dict(result)

            server_nonce = result['servernonce']
            iterations = int(result['iterations'])
            salt = result['salt']

            salted_password = hashlib.pbkdf2_hmac(
                'sha256',
                self._password.encode('utf-8'),
                bytearray.fromhex(salt),
                iterations,
                32
            )

            auth_msg = first_nonce + ',' + server_nonce + ',' + server_nonce
            client_key = hmac.new('Client Key'.encode('utf-8'), salted_password, hashlib.sha256).hexdigest()
            stored_key = hashlib.sha256(bytearray.fromhex(client_key)).hexdigest()
            client_signature = hmac.new(auth_msg.encode('utf-8'), bytearray.fromhex(stored_key),
                                        hashlib.sha256).hexdigest()

            client_proof = bytes(
                key ^ sign for (key, sign) in
                zip(bytearray.fromhex(client_key), bytearray.fromhex(client_signature)))

            _LOGGER.debug("Sending proof")
            response = await self._post_raw("api/system/user_login_proof",
                                            {"csrf": self._active_csrf,
                                             "data": {"clientproof": client_proof.hex(),
                                                      "finalnonce": server_nonce}})
            if response.status != 200:
                _LOGGER.error("Authentication failed: can not send proof, status is %s", response.status)
                raise AuthenticationError("Failed to send proof", AUTH_FAILURE_GENERAL)

            result = await _get_response_json(response)
            self._handle_csrf_dict(result)
            _handle_error_dict(result)

            _LOGGER.debug("Authentication success")
        except ApiCallError as ex:
            if ex.category == "user_pass_err":
                raise AuthenticationError("Invalid username or password", AUTH_FAILURE_CREDENTIALS)

            _LOGGER.warning("Authentication failed: %s", {str(ex)})
            raise AuthenticationError("Authentication failed due to api call error", AUTH_FAILURE_GENERAL)
        except Exception as ex:
            _LOGGER.warning("Authentication failed: %s", {str(ex)})
            raise AuthenticationError("Authentication failed due to unknown error", AUTH_FAILURE_GENERAL)

    async def get(self, path: str, **kwargs: Any) -> Dict:
        """Perform GET request to the relative address."""
        async with self._call_locker:
            await self._ensure_initialized()

            check_authorized = kwargs.get('check_authorized') or _check_authorized

            response = await self._get_raw(path)
            result = await _get_response_json(response)

            if not check_authorized(response, result):
                _LOGGER.debug("GET seems unauthorized, trying to re-authenticate")
                await self.authenticate()
                response = await self._get_raw(path)
                result = await _get_response_json(response)
                if not check_authorized(response, result):
                    raise ApiCallError(f"Api call error, status:{response.status}", -2, "unauthorized")

            self._handle_csrf_dict(result)
            _handle_error_dict(result)
            return result

    async def post(self, path: str, payload: Dict, **kwargs: Any) -> Dict:
        """Perform POST request to the relative address with the specified body."""
        async with self._call_locker:
            await self._ensure_initialized()

            check_authorized = kwargs.get('check_authorized') or _check_authorized

            dto = {"csrf": self._active_csrf, "data": payload}
            if kwargs.get('extra_data') is not None:
                for key, value in kwargs.get('extra_data', {}).items():
                    dto[key] = value

            response = await self._post_raw(path, dto)
            result = await _get_response_json(response)

            if not check_authorized(response, result):
                _LOGGER.debug("POST seems unauthorized, trying to re-authenticate")
                await self.authenticate()

                dto = {"csrf": self._active_csrf, "data": payload}
                if kwargs.get('extra_data') is not None:
                    for key, value in kwargs.get('extra_data', {}).items():
                        dto[key] = value

                response = await self._post_raw(path, dto)
                result = await _get_response_json(response)
                if not check_authorized(response, result):
                    raise ApiCallError(f"Api call error, status:{response.status}", -2, "unauthorized")

            self._handle_csrf_dict(result)
            _handle_error_dict(result)

            return result

    async def disconnect(self):
        """Close session."""
        _LOGGER.debug("Disconnecting")
        if self._session is not None:
            await self._session.close()
            self._session = None
