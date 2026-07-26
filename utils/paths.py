"""
Utility library for path management when using docker
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


PERSISTENT_DATA = ROOT / "persistent_data"

PERSISTENT_DATA.mkdir(exist_ok=True)

LOG_DIR = PERSISTENT_DATA / "logs"
DATABASE_DIR = PERSISTENT_DATA / "database"

LOG_DIR.mkdir(exist_ok=True)
DATABASE_DIR.mkdir(exist_ok=True)

DATABASE = DATABASE_DIR / "guild_api_database.db"
ANNI_PARTY_DATABASE = DATABASE_DIR / "anni_party.db"

PERSISTENT_DATA_CONFIGS = PERSISTENT_DATA / "configs"
PERSISTENT_CREDENTIAL_CONFIGS = PERSISTENT_DATA_CONFIGS / "credential_configs"

