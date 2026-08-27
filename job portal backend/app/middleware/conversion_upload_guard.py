from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request

from app.services.contact_security import client_ip
from app.services.document_conversion import (
    MAX_UPLOAD_BYTES,
    ConversionRejected,
    conversion_manager,
)

MAX_MULTIPART_BYTES = MAX_UPLOAD_BYTES + 256 * 1024


class ConversionUploadGuardMiddleware:
    """Rate-limit and size-bound converter bodies before multipart parsing."""

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
            or scope.get("path") != "/api/tools/document-converter/jobs"
        ):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        headers = request.headers
        try:
            content_length = int(headers.get("content-length", "0") or 0)
        except ValueError:
            content_length = 0
        if content_length > MAX_MULTIPART_BYTES:
            await self._reject(send, "The document must be smaller than 10 MB.", 413)
            return

        ip_key = hashlib.sha256(client_ip(request).encode("utf-8")).hexdigest()
        try:
            await conversion_manager.authorize_upload(ip_key)
        except ConversionRejected as exc:
            await self._reject(send, exc.message, exc.status_code, exc.retry_after)
            return

        chunks: list[bytes] = []
        total = 0
        more_body = True
        while more_body:
            message = await receive()
            if message.get("type") == "http.disconnect":
                return
            body = message.get("body", b"")
            total += len(body)
            if total > MAX_MULTIPART_BYTES:
                await self._reject(send, "The document must be smaller than 10 MB.", 413)
                return
            chunks.append(body)
            more_body = bool(message.get("more_body", False))

        scope.setdefault("state", {})["conversion_upload_authorized"] = True
        delivered = False

        async def replay_receive() -> dict[str, Any]:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return {"type": "http.disconnect"}

        await self.app(scope, replay_receive, send)

    @staticmethod
    async def _reject(
        send: Callable[[dict[str, Any]], Awaitable[None]],
        message: str,
        status_code: int,
        retry_after: int | None = None,
    ) -> None:
        body = json.dumps({"detail": message}).encode("utf-8")
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
        ]
        if retry_after:
            headers.append((b"retry-after", str(retry_after).encode("ascii")))
        await send({"type": "http.response.start", "status": status_code, "headers": headers})
        await send({"type": "http.response.body", "body": body})
