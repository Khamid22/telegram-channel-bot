from __future__ import annotations

from urllib.parse import urlencode

import requests
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/drive"]
AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"


def build_authorization_url(*, client_id: str, redirect_uri: str, state: str) -> str:
    return f"{AUTH_URI}?{urlencode({
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': ' '.join(SCOPES),
        'access_type': 'offline',
        'prompt': 'consent',
        'state': state,
    })}"


def exchange_code_for_tokens(*, client_id: str, client_secret: str, redirect_uri: str, code: str) -> dict:
    response = requests.post(
        TOKEN_URI,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=20,
    )
    if not response.ok:
        try:
            detail = response.json().get("error_description") or response.json().get("error")
        except ValueError:
            detail = response.text
        raise RuntimeError(f"Google Drive authorization failed: {detail}")
    return response.json()


def credentials_from_refresh_token(*, client_id: str, client_secret: str, refresh_token: str) -> Credentials:
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
