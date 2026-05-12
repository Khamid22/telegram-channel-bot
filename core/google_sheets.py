from __future__ import annotations

import json
import logging
from hashlib import sha1
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from config.settings import get_settings
from database.repositories import LogRepository, WordRepository

logger = logging.getLogger(__name__)

SHEET_COLUMNS = ["id", "word", "word_type", "phonetic", "definition", "example", "level", "accent", "status"]
HEADER_ALIASES = {
    "id": "id",
    "word": "word",
    "vocabulary": "word",
    "term": "word",
    "word_type": "word_type",
    "word type": "word_type",
    "type": "word_type",
    "part_of_speech": "word_type",
    "part of speech": "word_type",
    "pos": "word_type",
    "phonetic": "phonetic",
    "phonetics": "phonetic",
    "ipa": "phonetic",
    "definition": "definition",
    "meaning": "definition",
    "example": "example",
    "example sentence": "example",
    "level": "level",
    "accent": "accent",
    "status": "status",
}
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def _normalize_header(value: str) -> str:
    return " ".join(value.strip().lower().replace("-", " ").split())


def _stable_id(payload: dict[str, Any], row_number: int) -> str:
    base = f"{payload.get('word', '')}|{payload.get('definition', '')}".lower().strip()
    if not base:
        base = f"row-{row_number}"
    return f"auto-{sha1(base.encode('utf-8')).hexdigest()[:12]}"


def _row_to_payload(row: list[str], headers: list[str], row_number: int) -> dict[str, Any] | None:
    payload = {column: "" for column in SHEET_COLUMNS}
    for index, header in enumerate(headers):
        if header in payload and index < len(row):
            payload[header] = row[index].strip() if row[index] else ""

    if not payload["word"] or not payload["definition"]:
        return None
    if not payload["id"]:
        payload["id"] = _stable_id(payload, row_number)
    payload["status"] = payload["status"] or "new"
    return payload


def _headers_from_row(row: list[str]) -> list[str] | None:
    headers = [HEADER_ALIASES.get(_normalize_header(cell), "") for cell in row]
    has_required_columns = "word" in headers and "definition" in headers
    return headers if has_required_columns else None


class GoogleSheetsClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    def values(self) -> list[dict[str, Any]]:
        if not self.settings.google_sheet_id:
            raise RuntimeError("GOOGLE_SHEET_ID is not configured")
        if self.settings.google_service_account_json:
            credentials = Credentials.from_service_account_info(
                json.loads(self.settings.google_service_account_json),
                scopes=SCOPES,
            )
        elif self.settings.google_credentials_path.exists():
            credentials = Credentials.from_service_account_file(self.settings.google_credentials_path, scopes=SCOPES)
        else:
            raise RuntimeError(f"Google credentials file not found: {self.settings.google_credentials_path}")
        service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=self.settings.google_sheet_id, range=self.settings.google_sheet_range)
            .execute()
        )
        rows = result.get("values", [])
        if not rows:
            return []

        headers = _headers_from_row(rows[0])
        has_header_row = headers is not None
        data_rows = rows[1:] if has_header_row else rows
        if not headers:
            headers = ["word", "word_type", "definition", "example", "level"]

        start_row_number = 2 if has_header_row else 1
        return [payload for index, row in enumerate(data_rows, start=start_row_number) if (payload := _row_to_payload(row, headers, index))]


def sync_words_from_sheets(db: Session) -> int:
    rows = GoogleSheetsClient().values()
    words = WordRepository(db)
    logs = LogRepository(db)
    for row in rows:
        words.upsert_from_sheet(row)
    logs.add("sheets_sync", f"Synced {len(rows)} rows from Google Sheets")
    db.commit()
    logger.info("Synced %s Google Sheets rows", len(rows))
    return len(rows)
