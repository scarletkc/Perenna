from __future__ import annotations

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from perenna.oauth import JWTTokenVerifier


class _SigningKey:
    def __init__(self, key: object) -> None:
        self.key = key


class _JWKClient:
    def __init__(self, key: object) -> None:
        self._key = key

    def get_signing_key_from_jwt(self, _token: str) -> _SigningKey:
        return _SigningKey(self._key)


@pytest.mark.asyncio
async def test_jwt_verifier_accepts_only_the_configured_owner_and_resource(caplog) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = JWTTokenVerifier(
        issuer="https://tenant.example.com/",
        audience="https://memory.example.com/mcp",
        jwks_url="https://tenant.example.com/.well-known/jwks.json",
        allowed_subject="auth0|owner",
    )
    verifier._jwk_client = _JWKClient(private_key.public_key())  # type: ignore[assignment]
    now = int(time.time())
    claims = {
        "iss": "https://tenant.example.com/",
        "aud": "https://memory.example.com/mcp",
        "sub": "auth0|owner",
        "azp": "chatgpt-client",
        "iat": now,
        "exp": now + 300,
        "scope": "memory:read memory:write",
    }
    token = jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test"})

    access = await verifier.verify_token(token)

    assert access is not None
    assert access.client_id == "chatgpt-client"
    assert access.subject == "auth0|owner"
    assert access.resource == "https://memory.example.com/mcp"
    assert access.scopes == ["memory:read", "memory:write"]

    wrong_owner = jwt.encode(
        {**claims, "sub": "auth0|someone-else"},
        private_key,
        algorithm="RS256",
        headers={"kid": "test"},
    )
    wrong_audience = jwt.encode(
        {**claims, "aud": "https://other.example.com/mcp"},
        private_key,
        algorithm="RS256",
        headers={"kid": "test"},
    )
    wrong_issuer = jwt.encode(
        {**claims, "iss": "https://other.example.com/"},
        private_key,
        algorithm="RS256",
        headers={"kid": "test"},
    )
    expired = jwt.encode(
        {**claims, "iat": now - 600, "exp": now - 300},
        private_key,
        algorithm="RS256",
        headers={"kid": "test"},
    )
    not_yet_valid = jwt.encode(
        {**claims, "nbf": now + 300},
        private_key,
        algorithm="RS256",
        headers={"kid": "test"},
    )
    missing_subject = jwt.encode(
        {key: value for key, value in claims.items() if key != "sub"},
        private_key,
        algorithm="RS256",
        headers={"kid": "test"},
    )
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    bad_signature = jwt.encode(
        claims,
        other_key,
        algorithm="RS256",
        headers={"kid": "test"},
    )

    assert await verifier.verify_token(wrong_owner) is None
    assert await verifier.verify_token(wrong_audience) is None
    assert await verifier.verify_token(wrong_issuer) is None
    assert await verifier.verify_token(expired) is None
    assert await verifier.verify_token(not_yet_valid) is None
    assert await verifier.verify_token(missing_subject) is None
    assert await verifier.verify_token(bad_signature) is None
    assert await verifier.verify_token("not-a-jwt") is None
    assert token not in caplog.text
    assert wrong_owner not in caplog.text
