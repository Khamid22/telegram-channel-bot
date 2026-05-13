from __future__ import annotations

import html
import json
from typing import Any

from flask import jsonify
from googleapiclient.errors import HttpError


def _json(data: Any, status: int = 200):
    return jsonify(data), status


def _no_store(response):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def _drive_error_message(exc: Exception) -> str:
    if isinstance(exc, HttpError):
        try:
            payload = json.loads(exc.content.decode("utf-8"))
            detail = payload.get("error", {}).get("message")
            if detail:
                return detail
        except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
            pass
    return str(exc)


def _html_message(title: str, message: str, status: int = 200):
    escaped_title = html.escape(title)
    escaped_message = html.escape(message)
    return (
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 48px; color: #172033; }}
    a {{ color: #2357d9; }}
  </style>
</head>
<body>
  <h1>{escaped_title}</h1>
  <p>{escaped_message}</p>
  <p><a href="/">Return to admin</a></p>
</body>
</html>""",
        status,
        {"Content-Type": "text/html; charset=utf-8"},
    )
