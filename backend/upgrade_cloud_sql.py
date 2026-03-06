import os
import subprocess

# Point Alembic to Cloud SQL DB
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:kinpass@localhost:15432/kin"

subprocess.run([r".\venv\Scripts\alembic.exe", "upgrade", "head"], check=True)
