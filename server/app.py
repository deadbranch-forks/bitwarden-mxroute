import os
import re
import secrets
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime

import coolname
import httpx
import tldextract
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

# ── Environment config ──────────────────────────────────────

SERVER_API_TOKEN = os.getenv("SERVER_API_TOKEN")

MXROUTE_SERVER = os.getenv("MXROUTE_SERVER")
MXROUTE_USERNAME = os.getenv("MXROUTE_USERNAME")
MXROUTE_API_KEY = os.getenv("MXROUTE_API_KEY")

# ── Constants ────────────────────────────────────────────────

ALLOWED_TEMPLATE_PARTS = ["slug", "hex"]
DOMAIN_ERROR_MESSAGE = "The 'target' option must be a valid domain (e.g. example.com)."
TLD_EXTRACTOR = tldextract.TLDExtract(suffix_list_urls=())


# ── Helpers ──────────────────────────────────────────────────

def build_request(domain: str) -> tuple[str, dict[str, str]]:
    mxroute_endpoint = f"https://api.mxroute.com/domains/{domain}/forwarders"
    mxroute_headers = {
        "X-Server": MXROUTE_SERVER,
        "X-Username": MXROUTE_USERNAME,
        "X-API-Key": MXROUTE_API_KEY,
        "Content-Type": "application/json",
    }

    return mxroute_endpoint, mxroute_headers


def get_current_datetime() -> datetime:
    return datetime.now()


def build_domain_alias(target: str) -> str:
    normalized_target = target.strip().lower()
    extracted = TLD_EXTRACTOR(normalized_target)

    host = extracted.domain
    suffix = extracted.suffix
    if not host or not suffix:
        raise ValueError(DOMAIN_ERROR_MESSAGE)

    tld = suffix.split(".")[-1]
    host = host[:8]

    if (
        not re.fullmatch(r"[a-z0-9-]+", host)
        or not re.fullmatch(r"[a-z0-9-]+", tld)
    ):
        raise ValueError(DOMAIN_ERROR_MESSAGE)

    now = get_current_datetime()
    month = f"{now.month:02d}"
    year_last_digit = str(now.year % 10)
    week_in_month = ((now.day - 1) // 7) + 1

    return f"{tld}-{host}-{month}{year_last_digit}{week_in_month}"


def build_template_alias(
    template: str,
    alias_separator: str,
    slug_separator: str,
    slug_length: int,
    hex_length: int,
) -> str:
    template_parts = []
    for match in re.findall(r"<(.*?)>", template):
        template_parts.append(match)

    alias_parts = []
    for part in template_parts:
        if part not in ALLOWED_TEMPLATE_PARTS:
            raise ValueError(f"Template part '{part}' is not allowed.")

        match part:
            case "slug":
                if slug_length == 1:
                    alias_parts.append(coolname.generate(2)[0])
                else:
                    alias_parts.append(
                        slug_separator.join(coolname.generate(slug_length))
                    )
            case "hex":
                alias_parts.append(secrets.token_hex(hex_length)[:hex_length])

    return alias_separator.join(alias_parts)


def get_options(request_options: list[str]) -> tuple[str, str, str]:
    options: dict[str, str] = {}
    for option in request_options:
        if "=" in option:
            key, value = option.split("=", 1)
            options[key] = value

    domain = options.get("domain")
    destination = options.get("destination")
    target = options.get("target")
    if not domain or not destination or not target:
        raise ValueError(
            "The 'domain', 'destination', and 'target' options are required to be configured."
        )

    template = options.get("template")
    prefix = options.get("prefix", "")
    suffix = options.get("suffix", "")
    alias_separator = options.get("alias_separator", "_")

    if template:
        slug_separator = options.get("slug_separator", "_")
        slug_length = int(options.get("slug_length", "2"))
        hex_length = int(options.get("hex_length", "6"))
        alias = build_template_alias(
            template,
            alias_separator,
            slug_separator,
            slug_length,
            hex_length,
        )
    else:
        alias = build_domain_alias(target)

    if prefix != "":
        alias = f"{prefix}{alias_separator}{alias}"
    if suffix != "":
        alias += f"{alias_separator}{suffix}"

    return domain, destination, alias


# ── Auth middleware ──────────────────────────────────────────

class AuthMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        if not SERVER_API_TOKEN:
            response = JSONResponse({"error": "SERVER_API_TOKEN not configured"}, status_code=500)
            await response(scope, receive, send)
            return

        auth_value = None
        for key, val in scope.get("headers", []):
            if key == b"authorization":
                auth_value = val.decode()
                break

        if not auth_value or not auth_value.startswith("Bearer "):
            response = JSONResponse({"error": "Missing or invalid Authorization header"}, status_code=401)
            await response(scope, receive, send)
            return

        token = auth_value.split(" ", 1)[1]
        if token != SERVER_API_TOKEN:
            response = JSONResponse({"error": "Invalid token"}, status_code=401)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


# ── Lifespan ─────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: Starlette) -> AsyncGenerator[None]:
    app.state.http_client = httpx.AsyncClient()
    yield
    await app.state.http_client.aclose()


# ── Route handlers ───────────────────────────────────────────

async def status(request: Request) -> PlainTextResponse:
    return PlainTextResponse("Bitwarden Mxroute plugin is running healthy.")


async def add(request: Request) -> JSONResponse:
    body = await request.json()
    data = body.get("domain")

    try:
        domain, destination, alias = get_options(data.split(","))

        payload = {
            "alias": alias,
            "destinations": [destination],
        }

        endpoint, headers = build_request(domain)
        client = request.app.state.http_client

        response = await client.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()

        return JSONResponse({"data": {"email": f"{alias}@{domain}"}})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=412)
    except httpx.HTTPError as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def list_aliases(request: Request) -> JSONResponse:
    domain = request.path_params["domain"]
    endpoint, headers = build_request(domain)

    try:
        client = request.app.state.http_client
        response = await client.get(endpoint, headers=headers)
        response.raise_for_status()

        data = response.json()

        return JSONResponse(data["data"], status_code=response.status_code)
    except httpx.HTTPError as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def delete(request: Request) -> JSONResponse:
    email = request.path_params["email"]
    try:
        alias, domain = email.split("@")
    except ValueError:
        return JSONResponse({"error": "Invalid email format."}, status_code=400)

    endpoint, headers = build_request(domain)

    try:
        client = request.app.state.http_client
        response = await client.delete(f"{endpoint}/{alias}", headers=headers)
        response.raise_for_status()

        return JSONResponse({"message": "Deleted."}, status_code=response.status_code)
    except httpx.HTTPError as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── App construction ─────────────────────────────────────────

routes = [
    Route("/", status, methods=["GET"]),
    Route("/add/{subpath:path}", add, methods=["POST"]),
    Route("/list/{domain}", list_aliases, methods=["GET"]),
    Route("/delete/{email}", delete, methods=["DELETE"]),
]

middleware = [
    Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]),
    Middleware(AuthMiddleware),
]

app = Starlette(routes=routes, middleware=middleware, lifespan=lifespan)
