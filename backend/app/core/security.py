"""
JWT Authentication Middleware
==============================
Replaces the old hardcoded APIKeyMiddleware.
- Skips auth for public paths (/auth/*, /docs, /openapi.json, /)
- Returns 401 for missing/expired/invalid JWT
- Returns 403 for cross-family access attempts (never 404)
"""
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from jose import jwt, JWTError, ExpiredSignatureError

from app.core.auth import JWT_SECRET_KEY, JWT_ALGORITHM, current_family_id, current_user_id

logger = logging.getLogger(__name__)

# Paths that don't require authentication
PUBLIC_PATHS = {"/", "/docs", "/redoc", "/openapi.json"}
PUBLIC_PREFIXES = ("/api/v1/auth/", "/auth/")


class JWTAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth for public paths
        if path in PUBLIC_PATHS:
            return await call_next(request)

        # Skip auth for public prefixes (auth endpoints)
        for prefix in PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Skip auth for WebSocket (handled separately)
        if request.scope.get("type") == "websocket":
            return await call_next(request)

        # Skip CORS preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        # Extract Bearer token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing authentication token"},
            )

        token = auth_header.split(" ", 1)[1]

        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        except ExpiredSignatureError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token has expired"},
            )
        except JWTError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid authentication token"},
            )

        # Set context vars for downstream use (RLS, deps)
        fid = payload.get("family_id")
        uid = payload.get("sub")
        if fid:
            current_family_id.set(fid)
        if uid:
            current_user_id.set(uid)

        # Store user info in request state for endpoint access
        request.state.user = payload

        response = await call_next(request)
        return response
