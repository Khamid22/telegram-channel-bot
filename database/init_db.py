from sqlalchemy import inspect, select, text
from werkzeug.security import generate_password_hash

from config.settings import get_settings
from database.models import AdminUser, Template
from database.session import SessionLocal, engine, init_db


def ensure_schema_compatibility() -> None:
    """Add columns that were introduced after the initial schema was deployed."""
    inspector = inspect(engine)
    if "words" not in inspector.get_table_names():
        return

    word_columns = {column["name"] for column in inspector.get_columns("words")}
    with engine.begin() as connection:
        if "word_type" not in word_columns:
            connection.execute(text("ALTER TABLE words ADD COLUMN word_type VARCHAR(80)"))


def bootstrap_database() -> None:
    settings = get_settings()
    init_db()
    ensure_schema_compatibility()

    db = SessionLocal()
    try:
        admin = db.scalar(select(AdminUser).where(AdminUser.username == settings.default_admin_username))
        if not admin:
            db.add(
                AdminUser(
                    username=settings.default_admin_username,
                    password_hash=generate_password_hash(settings.default_admin_password),
                )
            )

        existing_active = db.scalar(select(Template).where(Template.is_active.is_(True)))
        default_template = db.scalar(select(Template).where(Template.name == "Default Editorial"))
        default_was_active = bool(default_template and default_template.is_active)
        if not default_template:
            db.add(
                Template(
                    name="Default Editorial",
                    image_path="assets/templates/default.png",
                    config_path="assets/templates/default.json",
                    is_active=False,
                )
            )

        new_words_template = db.scalar(select(Template).where(Template.name == "New Words Template"))
        created_new_words_template = new_words_template is None
        if not new_words_template:
            new_words_template = Template(
                name="New Words Template",
                image_path="assets/templates/new-words-template.png",
                config_path="assets/templates/new-words-template.json",
                is_active=True,
            )
            db.add(new_words_template)
        else:
            new_words_template.image_path = "assets/templates/new-words-template.png"
            new_words_template.config_path = "assets/templates/new-words-template.json"

        should_activate_new_words = created_new_words_template or default_was_active or existing_active is None
        if should_activate_new_words:
            for template in db.scalars(select(Template)).all():
                template.is_active = template.name == "New Words Template"

        db.commit()
    finally:
        db.close()
