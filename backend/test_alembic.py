import asyncio
import traceback
from alembic.config import Config
from alembic import command

def run():
    alembic_cfg = Config("alembic.ini")
    try:
        command.upgrade(alembic_cfg, "head")
        print("Success")
    except Exception as e:
        print("MIGRATION FAILED:")
        traceback.print_exc()

if __name__ == "__main__":
    run()
