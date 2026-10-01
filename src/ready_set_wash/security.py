"""Small ASGI security boundary that rejects oversized bodies before parsing."""

from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; "
    "img-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; "
    "base-uri 'none'; form-action 'self'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


class SecurityMiddleware:
    def __init__(self, app: ASGIApp, max_body_bytes: int = 8192) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def secure_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.update(SECURITY_HEADERS)
            await send(message)

        async def reject(message: str, status: int) -> None:
            await JSONResponse({"error": message}, status_code=status)(scope, receive, secure_send)

        if scope["method"] == "POST":
            headers = Headers(scope=scope)
            origin = headers.get("origin")
            if origin and origin != str(Request(scope).base_url).rstrip("/"):
                await reject("Cross-origin request rejected", 403)
                return
            if headers.get("content-type", "").split(";")[0] != "application/json":
                await reject("JSON required", 415)
                return
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > self.max_body_bytes:
                    await reject("Request too large", 413)
                    return
                if not message.get("more_body", False):
                    break
            replayed = False

            async def replay() -> Message:
                nonlocal replayed
                if not replayed:
                    replayed = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()

            await self.app(scope, replay, secure_send)
        else:
            await self.app(scope, receive, secure_send)
