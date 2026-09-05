from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any


MAX_STUDENT_API_AUTH_BODY_BYTES = 4096
AUTH_PATHS = {
    "/api/student-api/request-code",
    "/api/student-api/verify-code",
}


class StudentApiGuardMiddleware:
    """Reject oversized authentication bodies before JSON parsing.

    The student API service applies hashed per-IP, per-email, per-key and global
    request limits. This middleware is the cheaper first layer: a client cannot
    make the application buffer an arbitrarily large JSON body on either public
    credential endpoint.
    """

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        if (
            scope.get("type") != "http"
            or scope.get("method") != "POST"
            or scope.get("path") not in AUTH_PATHS
        ):
            await self.app(scope, receive, send)
            return

        raw_headers = dict(scope.get("headers") or [])
        try:
            content_length = int(raw_headers.get(b"content-length", b"0") or b"0")
        except ValueError:
            content_length = 0
        if content_length > MAX_STUDENT_API_AUTH_BODY_BYTES:
            await self._reject(send)
            return

        chunks: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            if message.get("type") == "http.disconnect":
                return
            body = message.get("body", b"")
            total += len(body)
            if total > MAX_STUDENT_API_AUTH_BODY_BYTES:
                await self._reject(send)
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break

        delivered = False

        async def replay_receive() -> dict[str, Any]:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {
                    "type": "http.request",
                    "body": b"".join(chunks),
                    "more_body": False,
                }
            return {"type": "http.disconnect"}

        await self.app(scope, replay_receive, send)

    @staticmethod
    async def _reject(send: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        body = json.dumps({"detail": "Request body is too large."}).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
