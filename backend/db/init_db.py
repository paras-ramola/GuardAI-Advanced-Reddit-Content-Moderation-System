"""
Database initialization script — creates tables from schema.sql.
Run: python -m db.init_db
"""
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def init_db():
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://moderator:password@localhost:5432/content_moderation"
    )

    # Parse URL for psycopg2
    from urllib.parse import urlparse
    parsed = urlparse(db_url)

    conn_params = {
        "host":     parsed.hostname or "localhost",
        "port":     parsed.port or 5432,
        "user":     parsed.username or "moderator",
        "password": parsed.password or "password",
        "dbname":   parsed.path.lstrip("/") or "content_moderation",
    }

    logger.info(f"Connecting to PostgreSQL at {conn_params['host']}:{conn_params['port']}")

    try:
        conn = psycopg2.connect(**conn_params)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        schema_path = Path(__file__).parent / "schema.sql"
        logger.info(f"Running schema: {schema_path}")
        cursor.execute(schema_path.read_text())

        # Check if we need to auto-load data
        cursor.execute("SELECT COUNT(1) FROM content")
        if cursor.fetchone()[0] == 0:
            logger.info("Database is completely empty. Auto-loading offline dataset...")
            from data.load_reddit_csv import load_csv
            csv_path = Path(__file__).resolve().parent.parent.parent / "reddit_data.csv"
            if csv_path.exists():
                logger.info(f"Adding All rows from {csv_path.name} to the database")
                load_csv(str(csv_path))
            else:
                logger.warning(f"Could not auto-load data: {csv_path} not found.")

        cursor.close()
        conn.close()
        logger.info("✅ Database initialized and verified.")

    except psycopg2.OperationalError as e:
        logger.error(f"❌ Could not connect to database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    init_db()
