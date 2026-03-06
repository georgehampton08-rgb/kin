from alembic.config import Config
from alembic import context
import os

alembic_cfg = Config("alembic.ini")

# override logic from env.py
_db_url = os.getenv("DATABASE_URL")
if _db_url:
    alembic_cfg.set_main_option("sqlalchemy.url", _db_url)

print("Alembic will connect to: ", alembic_cfg.get_main_option("sqlalchemy.url"))
