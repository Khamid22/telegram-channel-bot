from __future__ import annotations

import secrets

from flask import Blueprint, request, redirect, session as flask_session, url_for
from flask_login import login_required
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request as GoogleAuthRequest
from googleapiclient.discovery import build as build_google_service
from googleapiclient.errors import HttpError

from admin.serializers import collection_payload, source_payload
from admin.utils import _json, _drive_error_message, _html_message
from config.settings import get_settings
from database.repositories import (
    DriveSourceFileRepository,
    GoogleDriveCredentialRepository,
    VocabularyCollectionRepository,
)
from database.session import SessionLocal
from core.google_drive_auth import (
    build_authorization_url,
    credentials_from_refresh_token,
    exchange_code_for_tokens,
)
from core.vocabulary_generator import VocabularyGeneratorService

bp = Blueprint("drive", __name__)


def _redirect_uri() -> str:
    scheme = request.headers.get("X-Forwarded-Proto", request.scheme)
    return url_for("drive.oauth_callback", _external=True, _scheme=scheme)


@bp.get("/api/drive/oauth/status")
@login_required
def oauth_status():
    settings = get_settings()
    db = SessionLocal()
    try:
        credential = GoogleDriveCredentialRepository(db).active()
        return _json(
            {
                "configured": bool(settings.google_oauth_client_id and settings.google_oauth_client_secret),
                "connected": bool(credential),
                "account_email": credential.account_email if credential else None,
                "redirect_uri": _redirect_uri(),
                "root_folder_name": settings.google_drive_root_folder_name,
                "root_folder_id": settings.google_drive_root_folder_id or None,
            }
        )
    finally:
        db.close()


@bp.post("/api/drive/oauth/start")
@login_required
def oauth_start():
    settings = get_settings()
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        return _json({"error": "Configure GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET first."}, 400)
    state = secrets.token_urlsafe(32)
    flask_session["google_drive_oauth_state"] = state
    redirect_uri = _redirect_uri()
    return _json(
        {
            "authorization_url": build_authorization_url(
                client_id=settings.google_oauth_client_id,
                redirect_uri=redirect_uri,
                state=state,
            ),
            "redirect_uri": redirect_uri,
        }
    )


@bp.get("/api/drive/oauth/callback")
@login_required
def oauth_callback():
    settings = get_settings()
    if request.args.get("error"):
        return _html_message(
            "Google Drive Not Connected",
            request.args.get("error_description") or request.args["error"],
            400,
        )

    expected_state = flask_session.pop("google_drive_oauth_state", None)
    if not expected_state or request.args.get("state") != expected_state:
        return _html_message(
            "Google Drive Not Connected",
            "The authorization state did not match. Start the connection again.",
            400,
        )

    code = request.args.get("code")
    if not code:
        return _html_message("Google Drive Not Connected", "Google did not return an authorization code.", 400)

    db = SessionLocal()
    try:
        redirect_uri = _redirect_uri()
        tokens = exchange_code_for_tokens(
            client_id=settings.google_oauth_client_id,
            client_secret=settings.google_oauth_client_secret,
            redirect_uri=redirect_uri,
            code=code,
        )
        credential_repo = GoogleDriveCredentialRepository(db)
        existing = credential_repo.active()
        refresh_token = tokens.get("refresh_token") or (existing.refresh_token if existing else None)
        if not refresh_token:
            return _html_message(
                "Google Drive Not Connected",
                "Google did not return a refresh token. Start the connection again and approve offline access.",
                400,
            )

        credentials = credentials_from_refresh_token(
            client_id=settings.google_oauth_client_id,
            client_secret=settings.google_oauth_client_secret,
            refresh_token=refresh_token,
        )
        credentials.refresh(GoogleAuthRequest())
        about = (
            build_google_service("drive", "v3", credentials=credentials, cache_discovery=False)
            .about()
            .get(fields="user(emailAddress,displayName)")
            .execute()
        )
        user = about.get("user", {})
        credential_repo.save(
            refresh_token=refresh_token,
            account_email=user.get("emailAddress") or user.get("displayName"),
            scopes=tokens.get("scope"),
        )
        db.commit()
    except (RuntimeError, RefreshError, HttpError) as exc:
        db.rollback()
        return _html_message("Google Drive Not Connected", _drive_error_message(exc), 400)
    finally:
        db.close()

    return redirect("/#dashboard")


@bp.get("/api/drive/vocabulary")
@login_required
def vocabulary_catalog():
    db = SessionLocal()
    try:
        return _json(
            {
                "collections": [collection_payload(c) for c in VocabularyCollectionRepository(db).list()],
                "sources": [source_payload(s) for s in DriveSourceFileRepository(db).list()],
            }
        )
    finally:
        db.close()


@bp.post("/api/drive/refresh")
@login_required
def refresh_drive():
    db = SessionLocal()
    try:
        result = VocabularyGeneratorService(db).refresh_drive_catalog()
        return _json(
            {
                "collections": [collection_payload(c) for c in result["collections"]],
                "sources": [source_payload(s) for s in result["sources"]],
            }
        )
    except (HttpError, RuntimeError) as exc:
        return _json({"error": _drive_error_message(exc)}, 400)
    finally:
        db.close()
