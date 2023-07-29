from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette import status
from api import extentions

class TokenAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header == f"Bearer {extentions.AUTH_KEY}":
            # Authentication successful, proceed with the request handling
            response = await call_next(request)
            return response
        else:
            # Authentication failed, return a 401 Unauthorized response
            return JSONResponse({
                "success": False,
                "error": "Invalid or missing authentication token",
            }, status_code=status.HTTP_401_UNAUTHORIZED)
