from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

API_KEY = "SUPER_SECRET_KIN_API_KEY"

class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/v1/telemetry/ingest"):
            api_key = request.headers.get("X-API-Key")
            if not api_key or api_key != API_KEY:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing API Key"}
                )
        response = await call_next(request)
        return response
