"""Authenticated ASGI API; optional web dependencies stay outside core policy."""

from __future__ import annotations

import hmac
import json
from dataclasses import dataclass
from importlib.resources import files

from .service import ExecutionService, ServiceError


@dataclass(frozen=True)
class Principal:
    name: str
    permissions: frozenset[str] = frozenset()


def create_app(service: ExecutionService, credentials: dict[str, Principal]):
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response
    from starlette.routing import Route

    if not credentials or any(len(token) < 32 or not token.isascii() for token in credentials):
        raise ValueError("At least one ASCII bearer token of 32+ characters is required")
    credentials = dict(credentials)

    async def endpoint(request: Request):
        headers = {
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'none'",
            "Referrer-Policy": "no-referrer",
        }
        if request.url.path == "/health":
            return JSONResponse({"status": "ok"}, headers=headers)
        assets = {
            "/": ("dashboard.html", "text/html"),
            "/dashboard.js": ("dashboard.js", "text/javascript"),
            "/dashboard.css": ("dashboard.css", "text/css"),
        }
        if request.url.path in assets:
            name, media = assets[request.url.path]
            return Response(
                files("orqen").joinpath("web", name).read_text("utf-8"),
                media_type=media,
                headers=headers,
            )
        supplied = request.headers.get("authorization", "")
        principal = None
        for token, candidate in credentials.items():
            if hmac.compare_digest(supplied.encode(), f"Bearer {token}".encode()):
                principal = candidate
        if principal is None:
            return JSONResponse(
                {"error": "Authentication required"},
                status_code=401,
                headers={**headers, "WWW-Authenticate": "Bearer"},
            )
        try:
            if request.url.path == "/v1/tasks":
                data = service.catalog(principal.permissions)
            elif request.method == "POST":
                if request.headers.get("content-type", "").split(";")[0] != "application/json":
                    raise ServiceError(415, "Expected application/json")
                body = bytearray()
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > 16384:
                        raise ServiceError(413, "Request too large")
                try:
                    data = json.loads(body)
                except (ValueError, UnicodeError):
                    raise ServiceError(400, "Invalid JSON") from None
                if (
                    type(data) is not dict
                    or set(data) != {"task", "inputs"}
                    or type(data["task"]) is not str
                ):
                    raise ServiceError(400, "Expected task and inputs")
                data = await service.execute(
                    principal.name,
                    principal.permissions,
                    data["task"],
                    data["inputs"],
                    request.headers.get("idempotency-key", ""),
                )
            elif "run_id" in request.path_params:
                data = service.get(principal.name, request.path_params["run_id"])
            else:
                data = service.history(principal.name)
            return JSONResponse(data, headers=headers)
        except ServiceError as exc:
            return JSONResponse({"error": str(exc)}, status_code=exc.status, headers=headers)
        except Exception:
            return JSONResponse(
                {"error": "Execution unavailable; check run history before retrying"},
                status_code=500,
                headers=headers,
            )

    return Starlette(
        routes=[
            Route(path, endpoint, methods=methods)
            for path, methods in (
                ("/", ["GET"]),
                ("/health", ["GET"]),
                ("/dashboard.js", ["GET"]),
                ("/dashboard.css", ["GET"]),
                ("/v1/tasks", ["GET"]),
                ("/v1/runs", ["GET", "POST"]),
                ("/v1/runs/{run_id}", ["GET"]),
            )
        ]
    )
