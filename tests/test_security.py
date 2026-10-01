import asyncio

from ready_set_wash.security import SecurityMiddleware


def test_streaming_body_limit():
    async def run():
        called = False

        async def downstream(scope, receive, send):
            nonlocal called
            called = True

        chunks = iter(
            [
                {"type": "http.request", "body": b"x" * 5, "more_body": True},
                {"type": "http.request", "body": b"x" * 5, "more_body": False},
            ]
        )

        async def receive():
            return next(chunks)

        sent = []

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "path": "/graphql",
            "root_path": "",
            "server": ("localhost", 80),
            "headers": [(b"content-type", b"application/json")],
        }
        await SecurityMiddleware(downstream, max_body_bytes=8)(scope, receive, send)
        assert not called
        assert sent[0]["status"] == 413
        assert b"content-security-policy" in dict(sent[0]["headers"])

    asyncio.run(run())


def test_disconnect_and_replay():
    async def run():
        messages = iter(
            [
                {"type": "http.request", "body": b"{}", "more_body": False},
                {"type": "http.disconnect"},
            ]
        )

        async def receive():
            return next(messages)

        async def send(message):
            pass

        async def downstream(scope, receive, send):
            assert (await receive())["body"] == b"{}"
            assert (await receive())["type"] == "http.disconnect"

        scope = {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "path": "/graphql",
            "root_path": "",
            "server": ("localhost", 80),
            "headers": [(b"content-type", b"application/json")],
        }
        await SecurityMiddleware(downstream)(scope, receive, send)

        async def disconnected():
            return {"type": "http.disconnect"}

        await SecurityMiddleware(downstream)(scope, disconnected, send)

    asyncio.run(run())
