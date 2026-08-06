#!/usr/bin/env python3
"""Product API stand-in for the Account Concierge (trusted-backend ingress).

In production this is *any* server that already owns authentication — your
FastAPI/Flask/Django app, BFF, API gateway, etc. That server:

1. Authenticates the member however you already do (session cookie, OAuth,
   SSO, API key, …). MDA does not care about that mechanism.
2. Proxies LangGraph / agent traffic to the Account Concierge deployment.
3. Stamps reserved ingress headers on each upstream request:
     X-MDA-Ingress-Secret  ← shared secret (MDA_INGRESS_SECRET), server-only
     X-MDA-User-Id         ← the member id *your* auth layer resolved

The browser / mobile client never sees the ingress secret. MDA trusts the
secret, then scopes threads / memory to X-MDA-User-Id.

This file is a tiny stand-in for that pattern:
  GET /login?user=alice  → toy httpOnly session
  /threads, /runs, …     → proxy with the headers above
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import time
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
SESSION_COOKIE = "mda_tb_session"
PROXY_PREFIXES = (
    "/threads",
    "/runs",
    "/assistants",
    "/info",
    "/ok",
    "/identity",
    "/store",
)

# user_id → created_at; keyed by session id
_sessions: dict[str, dict[str, Any]] = {}


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("#"):
            continue
        eq = trimmed.find("=")
        if eq == -1:
            continue
        key = trimmed[:eq].strip()
        value = trimmed[eq + 1 :].strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        os.environ.setdefault(key, value)


load_dotenv(ROOT / ".env")

PORT = int(os.environ.get("PROXY_PORT", "4910"))
# Prefer IPv6 loopback: langgraph-cli often binds `::1` only.
UPSTREAM = os.environ.get("LANGGRAPH_API_URL", "http://[::1]:2024").rstrip("/")
INGRESS_SECRET = os.environ.get("MDA_INGRESS_SECRET", "").strip()


def parse_cookies(cookie_header: str | None) -> dict[str, str]:
    if not cookie_header:
        return {}
    jar = SimpleCookie()
    jar.load(cookie_header)
    return {key: morsel.value for key, morsel in jar.items()}


def resolve_session(handler: BaseHTTPRequestHandler) -> dict[str, Any] | None:
    session_id = parse_cookies(handler.headers.get("Cookie")).get(SESSION_COOKIE)
    if not session_id:
        return None
    return _sessions.get(session_id)


def should_proxy(pathname: str) -> bool:
    return any(pathname == prefix or pathname.startswith(f"{prefix}/") for prefix in PROXY_PREFIXES)


class TrustedBackendHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        message = format % args
        sys.stderr.write(f"{self.address_string()} - {message}\n")

    def _send_json(
        self,
        status: int,
        body: object,
        *,
        extra_headers: list[tuple[str, str]] | None = None,
    ) -> None:
        payload = json.dumps(body, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        if extra_headers:
            for name, value in extra_headers:
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(payload)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def do_GET(self) -> None:
        self._dispatch()

    def do_POST(self) -> None:
        self._dispatch()

    def do_PUT(self) -> None:
        self._dispatch()

    def do_PATCH(self) -> None:
        self._dispatch()

    def do_DELETE(self) -> None:
        self._dispatch()

    def _dispatch(self) -> None:
        parsed = urlparse(self.path)
        pathname = parsed.path or "/"

        if pathname in {"/", "/health"}:
            session = resolve_session(self)
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "upstream": UPSTREAM,
                    "ingressSecretConfigured": bool(INGRESS_SECRET),
                    "session": None if session is None else session["user_id"],
                },
            )
            return

        # --- Demo auth surface (replace with your real login / session APIs) ---

        if pathname == "/login" and self.command == "GET":
            # Toy login: trust ?user= and mint a session. Production would verify
            # password, OAuth code, SSO assertion, etc., then store that user id.
            user = (parse_qs(parsed.query).get("user") or [""])[0].strip()
            if not user:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "missing_user", "hint": "GET /login?user=alice"},
                )
                return
            session_id = secrets.token_hex(16)
            _sessions[session_id] = {"user_id": user, "created_at": time.time()}
            self._send_json(
                HTTPStatus.OK,
                {"ok": True, "user": user},
                extra_headers=[
                    (
                        "Set-Cookie",
                        f"{SESSION_COOKIE}={session_id}; HttpOnly; Path=/; SameSite=Lax",
                    )
                ],
            )
            return

        if pathname == "/logout" and self.command in {"GET", "POST"}:
            session_id = parse_cookies(self.headers.get("Cookie")).get(SESSION_COOKIE)
            if session_id:
                _sessions.pop(session_id, None)
            self._send_json(
                HTTPStatus.OK,
                {"ok": True},
                extra_headers=[
                    (
                        "Set-Cookie",
                        f"{SESSION_COOKIE}=; HttpOnly; Path=/; Max-Age=0; SameSite=Lax",
                    )
                ],
            )
            return

        if pathname == "/me":
            session = resolve_session(self)
            if session is None:
                self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "not_authenticated"})
                return
            self._send_json(HTTPStatus.OK, {"user": session["user_id"]})
            return

        # --- Agent traffic: authenticate locally, then proxy with MDA headers ---

        if should_proxy(pathname):
            self._proxy_to_upstream()
            return

        self._send_json(
            HTTPStatus.NOT_FOUND,
            {
                "error": "not_found",
                "routes": ["/", "/login?user=", "/logout", "/me", *PROXY_PREFIXES],
            },
        )

    def _proxy_to_upstream(self) -> None:
        # Gate on *your* auth. MDA never sees the cookie / OAuth token — only headers.
        session = resolve_session(self)
        if session is None:
            self._send_json(
                HTTPStatus.UNAUTHORIZED,
                {
                    "error": "not_authenticated",
                    "hint": "GET /login?user=alice first",
                },
            )
            return
        if not INGRESS_SECRET:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {
                    "error": "missing_MDA_INGRESS_SECRET",
                    "hint": "Set MDA_INGRESS_SECRET in .env (same value as mda dev / deploy).",
                },
            )
            return

        # Preserve path + query from the client request.
        target = UPSTREAM + self.path

        headers: dict[str, str] = {}
        for key, value in self.headers.items():
            lower = key.lower()
            if lower in {"host", "connection", "content-length", "transfer-encoding"}:
                continue
            headers[key] = value
        # Trusted-backend ingress — required on every agent call from your backend.
        headers["X-MDA-Ingress-Secret"] = INGRESS_SECRET
        headers["X-MDA-User-Id"] = str(session["user_id"])

        body = self._read_body()
        request = Request(target, data=body or None, headers=headers, method=self.command)
        try:
            # Demo proxy: UPSTREAM is local mda or a configured deployment URL.
            with urlopen(request, timeout=600) as upstream:
                payload = upstream.read()
                self.send_response(upstream.status)
                for key, value in upstream.headers.items():
                    lower = key.lower()
                    if lower in {"transfer-encoding", "connection", "content-encoding"}:
                        continue
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
        except HTTPError as exc:
            payload = exc.read()
            self.send_response(exc.code)
            for key, value in exc.headers.items():
                lower = key.lower()
                if lower in {"transfer-encoding", "connection", "content-encoding"}:
                    continue
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except URLError as exc:
            self._send_json(
                HTTPStatus.BAD_GATEWAY,
                {
                    "error": "upstream_unreachable",
                    "message": str(exc.reason),
                    "upstream": UPSTREAM,
                },
            )


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), TrustedBackendHandler)
    sys.stderr.write(f"account-concierge proxy on http://127.0.0.1:{PORT}\n")
    sys.stderr.write(f"  upstream: {UPSTREAM}\n")
    sys.stderr.write(
        f"  login:    curl -c cookies.txt 'http://127.0.0.1:{PORT}/login?user=alice'\n"
    )
    if not INGRESS_SECRET:
        sys.stderr.write("  warning: MDA_INGRESS_SECRET is not set\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\n")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
