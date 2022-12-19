import hashlib
import hmac
from random import randbytes


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
