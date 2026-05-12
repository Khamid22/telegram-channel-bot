from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload, MediaIoBaseUpload

from config.settings import get_settings

FOLDER_MIME = "application/vnd.google-apps.folder"
CSV_MIME_TYPES = {"text/csv", "application/csv", "application/vnd.ms-excel"}
SCOPES = ["https://www.googleapis.com/auth/drive"]


@dataclass(slots=True)
class DriveItem:
    id: str
    name: str
    mime_type: str
    parents: list[str]


def _escape_query(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value.lower()).strip("-") or "collection"


class GoogleDriveStorage:
    def __init__(self) -> None:
        self.settings = get_settings()
        if self.settings.google_service_account_json:
            credentials = Credentials.from_service_account_info(
                json.loads(self.settings.google_service_account_json),
                scopes=SCOPES,
            )
        elif self.settings.google_credentials_path.exists():
            credentials = Credentials.from_service_account_file(self.settings.google_credentials_path, scopes=SCOPES)
        else:
            raise RuntimeError(f"Google Drive credentials file not found: {self.settings.google_credentials_path}")
        self.service = build("drive", "v3", credentials=credentials, cache_discovery=False)

    def ensure_root_structure(self) -> dict[str, object]:
        root_id = self.settings.google_drive_root_folder_id or self.ensure_folder(self.settings.google_drive_root_folder_name)
        vocabulary_id = self.ensure_folder("vocabulary", root_id)
        templates_id = self.ensure_folder("templates", vocabulary_id)

        collections = []
        known_names = {"new-words", "idioms"}
        for name in sorted(known_names):
            folder_id = self.ensure_folder(name, vocabulary_id)
            collections.append(self.ensure_collection_folders(name, folder_id))

        for folder in self.list_folders(vocabulary_id):
            if folder.name == "templates" or folder.name in known_names:
                continue
            collections.append(self.ensure_collection_folders(folder.name, folder.id))

        return {
            "root_id": root_id,
            "vocabulary_id": vocabulary_id,
            "templates_id": templates_id,
            "collections": collections,
        }

    def ensure_collection_folders(self, name: str, folder_id: str) -> dict[str, str]:
        return {
            "name": name,
            "slug": _slug(name),
            "drive_folder_id": folder_id,
            "source_folder_id": self.ensure_folder("source-files", folder_id),
            "generated_folder_id": self.ensure_folder("generated-posts", folder_id),
        }

    def ensure_folder(self, name: str, parent_id: str | None = None) -> str:
        query = [
            f"name = '{_escape_query(name)}'",
            f"mimeType = '{FOLDER_MIME}'",
            "trashed = false",
        ]
        if parent_id:
            query.append(f"'{_escape_query(parent_id)}' in parents")
        result = (
            self.service.files()
            .list(
                q=" and ".join(query),
                spaces="drive",
                fields="files(id,name,mimeType,parents)",
                pageSize=1,
            )
            .execute()
        )
        files = result.get("files", [])
        if files:
            return files[0]["id"]

        metadata = {"name": name, "mimeType": FOLDER_MIME}
        if parent_id:
            metadata["parents"] = [parent_id]
        created = self.service.files().create(body=metadata, fields="id").execute()
        return created["id"]

    def list_folders(self, parent_id: str) -> list[DriveItem]:
        query = f"'{_escape_query(parent_id)}' in parents and mimeType = '{FOLDER_MIME}' and trashed = false"
        return self._list(query)

    def list_files(self, parent_id: str, mime_types: Iterable[str] | None = None) -> list[DriveItem]:
        query = [f"'{_escape_query(parent_id)}' in parents", "trashed = false"]
        if mime_types:
            values = " or ".join(f"mimeType = '{_escape_query(mime)}'" for mime in mime_types)
            query.append(f"({values})")
        return self._list(" and ".join(query))

    def upload_bytes(self, data: bytes, *, name: str, parent_id: str, mime_type: str) -> DriveItem:
        media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime_type, resumable=False)
        created = (
            self.service.files()
            .create(
                body={"name": name, "parents": [parent_id]},
                media_body=media,
                fields="id,name,mimeType,parents",
            )
            .execute()
        )
        return self._item(created)

    def upload_file(self, path: Path, *, name: str, parent_id: str, mime_type: str) -> DriveItem:
        media = MediaFileUpload(str(path), mimetype=mime_type, resumable=False)
        created = (
            self.service.files()
            .create(
                body={"name": name, "parents": [parent_id]},
                media_body=media,
                fields="id,name,mimeType,parents",
            )
            .execute()
        )
        return self._item(created)

    def metadata(self, file_id: str) -> DriveItem:
        payload = self.service.files().get(fileId=file_id, fields="id,name,mimeType,parents").execute()
        return self._item(payload)

    def download_bytes(self, file_id: str) -> bytes:
        request = self.service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue()

    def download_to_path(self, file_id: str, path: Path) -> Path:
        path.write_bytes(self.download_bytes(file_id))
        return path

    def _list(self, query: str) -> list[DriveItem]:
        items: list[DriveItem] = []
        page_token = None
        while True:
            result = (
                self.service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="nextPageToken,files(id,name,mimeType,parents)",
                    pageToken=page_token,
                    pageSize=200,
                )
                .execute()
            )
            items.extend(self._item(payload) for payload in result.get("files", []))
            page_token = result.get("nextPageToken")
            if not page_token:
                break
        return items

    @staticmethod
    def _item(payload: dict[str, object]) -> DriveItem:
        return DriveItem(
            id=str(payload["id"]),
            name=str(payload.get("name", "")),
            mime_type=str(payload.get("mimeType", "")),
            parents=[str(parent) for parent in payload.get("parents", []) or []],
        )
