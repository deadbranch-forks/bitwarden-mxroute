import os
import re
import secrets
from datetime import datetime
from typing import Dict

import coolname
import requests
import tldextract
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

SERVER_API_TOKEN = os.getenv("SERVER_API_TOKEN")

MXROUTE_SERVER = os.getenv("MXROUTE_SERVER")
MXROUTE_USERNAME = os.getenv("MXROUTE_USERNAME")
MXROUTE_API_KEY = os.getenv("MXROUTE_API_KEY")

ALLOWED_TEMPLATE_PARTS = ["slug", "hex"]
DOMAIN_ERROR_MESSAGE = "The 'target' option must be a valid domain (e.g. example.com)."
TLD_EXTRACTOR = tldextract.TLDExtract(suffix_list_urls=())


def build_request(domain):
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


def get_options(request_options) -> tuple[str, str, str]:
    options: Dict[str, str] = {}
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


@app.before_request
def check_auth():
    if request.method == "OPTIONS":
        return

    auth_header = request.headers.get("Authorization")
    if not SERVER_API_TOKEN:
        return jsonify({"error": "SERVER_API_TOKEN not configured"}), 500

    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    token = auth_header.split(" ")[1]
    if token != SERVER_API_TOKEN:
        return jsonify({"error": "Invalid token"}), 401


@app.route("/")
def status():
    return "Bitwarden Mxroute plugin is running healthy."


@app.route("/add/<path:subpath>", methods=["POST"])
def add(subpath):
    data = request.get_json().get("domain")

    try:
        domain, destination, alias = get_options(data.split(","))

        body = {
            "alias": alias,
            "destinations": [destination],
        }

        endpoint, headers = build_request(domain)

        response = requests.post(endpoint, headers=headers, json=body)
        response.raise_for_status()

        return {"data": {"email": f"{alias}@{domain}"}}
    except ValueError as e:
        return jsonify({"error": str(e)}), 412
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


@app.route("/list/<domain>", methods=["GET"])
def get(domain):
    endpoint, headers = build_request(domain)

    try:
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()

        data = response.json()

        return jsonify(data["data"]), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


@app.route("/delete/<email>", methods=["DELETE"])
def delete(email):
    try:
        alias, domain = email.split("@")
    except ValueError:
        return jsonify({"error": "Invalid email format."}), 400

    endpoint, headers = build_request(domain)

    try:
        response = requests.delete(f"{endpoint}/{alias}", headers=headers)
        response.raise_for_status()

        return jsonify({"message": "Deleted."}), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500
