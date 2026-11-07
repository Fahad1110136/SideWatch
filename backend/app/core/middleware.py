import uuid

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse

BODY_METHODS = {"POST", "PUT", "PATCH"}
DOCS_PREFIXES = ("/api/docs", "/openapi.json")  # Swagger UI needs scripts, so no strict CSP there

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Cross-Origin-Resource-Policy": "same-origin",
}
API_CSP = "default-src 'none'; frame-ancestors 'none'"
PAGE_CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")


class BodySizeLimitMiddleware:
    def __init__(self, app, max_bytes: int = 65536):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in BODY_METHODS:
            await self.app(scope, receive, send)
            return

        headers = dict(scope["headers"])
        length = headers.get(b"content-length")
        if length is not None:
            try:
                too_big = int(length) > self.max_bytes
            except ValueError:
                too_big = True
            if too_big:
                await self._reject(scope, receive, send, 413, "REQUEST_TOO_LARGE",
                                   "Request body is too large.")
                return
        elif b"transfer-encoding" in headers:
            await self._reject(scope, receive, send, 411, "LENGTH_REQUIRED",
                               "Content-Length is required.")
            return
        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(scope, receive, send, status, code, message):
        body = {"code": code, "message": message, "request_id": uuid.uuid4().hex[:12]}
        await JSONResponse(body, status_code=status)(scope, receive, send)


class SecurityHeadersMiddleware:
    def __init__(self, app, hsts: bool = False):
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope["path"]

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for key, value in SECURITY_HEADERS.items():
                    headers[key] = value
                if not path.startswith(DOCS_PREFIXES):
                    headers["Content-Security-Policy"] = (
                        API_CSP if path.startswith("/api/") else PAGE_CSP)
                # if not path.startswith(DOCS_PREFIXES):
                #     headers["Content-Security-Policy"] = API_CSP
                if self.hsts:
                    headers["Strict-Transport-Security"] = "max-age=31536000"
            await send(message)

        await self.app(scope, receive, send_with_headers)