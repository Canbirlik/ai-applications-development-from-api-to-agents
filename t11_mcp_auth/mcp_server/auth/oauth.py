import os

import httpx
from jose import jwt, JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# ==================== CONFIGURATION ====================

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8089")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "mcp-realm")
REQUIRED_ROLE = os.getenv("MCP_REQUIRED_ROLE", "mcp-tools-access")

ISSUER = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}"
JWKS_URL = f"{ISSUER}/protocol/openid-connect/certs"

# ==================== JWKS CACHE ====================

# Public keys are fetched once from Keycloak and cached in memory.
# This avoids a round-trip to Keycloak on every MCP request.
# Cache is invalidated on server restart; for production you'd add TTL-based refresh.
_jwks_cache: dict | None = None


async def _get_jwks() -> dict:
    """Fetch and cache Keycloak public keys (JWKS)"""
    global _jwks_cache
    #TODO:
    # 1. If `_jwks_cache` is None — fetch it with an HTTP GET to `JWKS_URL`,
    #    call `.raise_for_status()`, parse the JSON, and store it in `_jwks_cache`
    #    Print "🔑 Fetching JWKS from ..." before and "🔑 JWKS cached successfully" after
    # 2. Return `_jwks_cache`
    if _jwks_cache is None:
        print(f"🔑 Fetching JWKS from {JWKS_URL}")
        async with httpx.AsyncClient() as client:
            response = await client.get(JWKS_URL)
            response.raise_for_status()
            _jwks_cache = response.json()
        print("🔑 JWKS cached successfully")

    assert _jwks_cache is not None
    return _jwks_cache


# ==================== MIDDLEWARE ====================

class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that:
      1. Extracts the Bearer token from the Authorization header
      2. Validates JWT signature using Keycloak public keys (JWKS)
      3. Verifies token issuer and expiry
      4. Checks that the user has the required realm role
    """

    async def dispatch(self, request: Request, call_next):
        auth_header = request.headers.get("Authorization", "")

        # ── Step 1: Check header presence ──────────────────────────────
        #TODO: If `auth_header` doesn't start with "Bearer " — return a 401 JSONResponse
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized: missing Bearer token"},
            )

        token = auth_header.removeprefix("Bearer ")

        # ── Step 2: Validate JWT signature + claims ─────────────────────
        #TODO:
        # 1. Fetch JWKS via `_get_jwks()`
        # 2. Decode the token with `jwt.decode` using algorithm `RS256`, the fetched JWKS,
        #    `issuer=ISSUER`, and `options={"verify_aud": False}`
        #    Wrap in try/except for `JWTError` and return a 401 JSONResponse on failure
        jwks = await _get_jwks()
        try:
            claims = jwt.decode(
                token,
                jwks,
                algorithms=["RS256"],
                issuer=ISSUER,
                options={"verify_aud": False},
            )
        except JWTError as e:
            return JSONResponse(
                status_code=401,
                content={"error": f"Unauthorized: invalid token ({e})"},
            )

        # ── Step 3: Check realm role ────────────────────────────────────
        # Keycloak embeds roles in: claims["realm_access"]["roles"]
        #TODO:
        # 1. Extract the list of realm roles from the decoded claims
        # 2. If `REQUIRED_ROLE` is not present — return a 403 JSONResponse listing the user's roles
        # 3. Print the authenticated username and their roles, then pass the request to the next handler
        roles = claims.get("realm_access", {}).get("roles", [])

        if REQUIRED_ROLE not in roles:
            return JSONResponse(
                status_code=403,
                content={"error": f"Forbidden: missing required role '{REQUIRED_ROLE}'", "roles": roles},
            )

        print(f"✅ Authenticated user '{claims.get('preferred_username')}' with roles {roles}")

        return await call_next(request)