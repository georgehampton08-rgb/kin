"""
HTTP Security Headers Middleware
=================================
Injects security headers on every response to mitigate:
  - XSS, clickjacking, MIME sniffing, protocol downgrade attacks

CSP policy is configurable via CSP_POLICY environment variable.
"""
import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Build CSP from environment or use strict default
_CSP_DEFAULT = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'"
)
CSP_POLICY = os.getenv("CSP_POLICY", _CSP_DEFAULT)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = CSP_POLICY

        return response
