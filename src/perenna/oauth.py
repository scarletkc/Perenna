from __future__ import annotations

import logging
from typing import Any

import anyio
import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken

logger = logging.getLogger(__name__)


class JWTTokenVerifier:
    """Verify one self-hosted Perenna owner's RS256 access tokens."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_url: str,
        allowed_subject: str,
    ) -> None:
        self._issuer = issuer
        self._audience = audience
        self._allowed_subject = allowed_subject
        self._jwk_client = PyJWKClient(
            jwks_url,
            cache_keys=True,
            max_cached_keys=16,
            cache_jwk_set=True,
            lifespan=300,
            timeout=5,
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        return await anyio.to_thread.run_sync(self._verify_token_sync, token)

    def _verify_token_sync(self, token: str) -> AccessToken | None:
        if token.count(".") != 2:
            logger.info("oauth_token=invalid reason=format")
            return None

        try:
            signing_key = self._jwk_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                key=signing_key.key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
                options={
                    "require": ["exp", "iat", "sub"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_nbf": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )
        except Exception as exc:
            logger.info(
                "oauth_token=invalid reason=verification error_type=%s",
                type(exc).__name__,
            )
            return None

        subject = claims.get("sub")
        if subject != self._allowed_subject:
            logger.warning("oauth_token=denied reason=subject")
            return None

        scopes = _extract_scopes(claims)
        client_id = claims.get("azp") or claims.get("client_id") or "oauth-client"
        return AccessToken(
            token=token,
            client_id=str(client_id),
            scopes=scopes,
            expires_at=claims.get("exp"),
            resource=self._audience,
            subject=str(subject),
            claims=claims,
        )


def _extract_scopes(claims: dict[str, Any]) -> list[str]:
    raw = claims.get("scope") or claims.get("scp")
    if isinstance(raw, str):
        return raw.split()
    if isinstance(raw, list | tuple):
        return [str(item) for item in raw]
    return []
