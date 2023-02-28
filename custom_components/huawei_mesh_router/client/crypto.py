import base64
import hashlib
import hmac
import math
from random import randbytes

from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA

from .classes import HuaweiRsaPublicKey

_RSA_CHUNK_SIZE = 214


# ---------------------------
#   CryptographyError
# ---------------------------
class CryptographyError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


def generate_nonce() -> str:
    """Return client nonce."""
    return randbytes(32).hex()


def get_client_proof(
    password: str, salt: str, iterations: int, first_nonce: str, server_nonce: str
) -> str:
    """Return client proof."""
    salted_password = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytearray.fromhex(salt),
        iterations,
        32,
    )

    auth_msg = first_nonce + "," + server_nonce + "," + server_nonce

    client_key = hmac.new(
        "Client Key".encode("utf-8"), salted_password, hashlib.sha256
    ).digest()

    stored_key = hashlib.sha256(client_key).digest()

    client_signature = hmac.new(
        auth_msg.encode("utf-8"), stored_key, hashlib.sha256
    ).digest()

    client_proof = bytes(
        key ^ sign for (key, sign) in zip(client_key, client_signature)
    )

    return client_proof.hex()


def rsa_encode(data: str, rsa_key: HuaweiRsaPublicKey) -> str:
    """Encode string with RSA."""
    n = int(rsa_key.rsan, 16)
    e = int(rsa_key.rsae, 16)

    public_key = RSA.construct((n, e)).public_key()
    encryptor = PKCS1_OAEP.new(public_key)

    data_base64 = base64.b64encode(data.encode("utf-8"))

    chunks_count = math.ceil(len(data_base64) / _RSA_CHUNK_SIZE)
    result = ""

    i = 0
    max_length_errors_count = 10
    while i < chunks_count:
        index = i * _RSA_CHUNK_SIZE
        chunk = data_base64[index : index + _RSA_CHUNK_SIZE]
        encoded_chunk = encryptor.encrypt(chunk).hex()
        if len(encoded_chunk) != len(rsa_key.rsan):
            max_length_errors_count -= 1
            if max_length_errors_count < 0:
                raise CryptographyError("Too many encoded chunk length errors.")
            continue
        i += 1
        result += encoded_chunk

    return result
