from __future__ import annotations

from flask import Blueprint, request
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash

from admin.extensions import login_manager
from admin.utils import _json
from database.repositories import AdminRepository
from database.session import SessionLocal

bp = Blueprint("auth", __name__)


@login_manager.user_loader
def load_user(user_id: str):
    db = SessionLocal()
    try:
        return AdminRepository(db).by_id(int(user_id))
    finally:
        db.close()


@bp.get("/api/health")
def health():
    return _json({"ok": True})


@bp.post("/api/auth/login")
def login():
    data = request.get_json(force=True)
    username = data.get("username", "")
    password = data.get("password", "")
    db = SessionLocal()
    try:
        user = AdminRepository(db).by_username(username)
        if not user or not check_password_hash(user.password_hash, password):
            return _json({"error": "Invalid username or password"}, 401)
        login_user(user)
        return _json({"user": {"id": user.id, "username": user.username}})
    finally:
        db.close()


@bp.post("/api/auth/logout")
@login_required
def logout():
    logout_user()
    return _json({"ok": True})


@bp.get("/api/me")
def me():
    if not current_user.is_authenticated:
        return _json({"user": None}, 401)
    return _json({"user": {"id": current_user.id, "username": current_user.username}})
