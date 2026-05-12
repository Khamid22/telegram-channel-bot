from admin.app import create_app
from config.logging import configure_logging
from database.init_db import bootstrap_database

configure_logging()
bootstrap_database()

# Keep one web worker in production so the embedded scheduler is not duplicated.
app = create_app(start_background_scheduler=True)
