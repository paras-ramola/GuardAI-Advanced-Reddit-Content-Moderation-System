"""
Bulk Reddit CSV loader — efficiently imports 1.9M rows into PostgreSQL.

Strategy:
  1. Stream CSV in chunks (no RAM overflow)
  2. Clean each chunk (bots, markdown, short text, etc.)
  3. Deduplicate within chunk
  4. Bulk insert using PostgreSQL COPY (fastest method, ~100K rows/sec)

Run:
    python -m data.load_reddit_csv --csv /path/to/reddit.csv [--sample 100000]

CSV expected columns: subreddit, body, score, controversiality
"""
import sys
import os
import re
import logging
import argparse
import time
from pathlib import Path
from io import StringIO

import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("loader")

# ─── Cleaning params ──────────────────────────────────────────────────────────
MIN_WORDS        = 3       # drop comments shorter than 3 words
MAX_CHARS        = 2000    # truncate very long comments
CHUNK_SIZE       = 50_000  # rows per chunk

BOT_PATTERNS = re.compile(
    r"i am a bot|this action was performed|if you have any questions|"
    r"\[deleted\]|\[removed\]|automoderator|please contact the moderators",
    re.IGNORECASE
)


def clean_text(text: str) -> str | None:
    """
    Clean a single Reddit comment body.
    Returns None if the comment should be dropped.
    """
    if not isinstance(text, str):
        return None

    # Drop bot messages / deleted content
    if BOT_PATTERNS.search(text):
        return None

    # Remove markdown links: [text](url) → text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove bare URLs
    text = re.sub(r'https?://\S+', '', text)
    # Remove Reddit-specific formatting: > quotes, **bold**, *italic*, ~~strike~~
    text = re.sub(r'^>.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'[*~`#]', '', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Truncate
    text = text[:MAX_CHARS]

    # Drop if too short
    if len(text.split()) < MIN_WORDS:
        return None

    return text


def clean_chunk(df: pd.DataFrame) -> pd.DataFrame:
    """Apply cleaning to a DataFrame chunk."""
    df = df.copy()

    # Keep only needed columns (handle missing columns gracefully)
    needed = {"subreddit", "body"}
    if not needed.issubset(df.columns):
        raise ValueError(f"CSV missing required columns. Found: {list(df.columns)}")

    df["body"]            = df["body"].apply(clean_text)
    df                    = df.dropna(subset=["body"])
    df["subreddit"]       = df["subreddit"].str.strip().str.lower()
    df["score"]           = pd.to_numeric(df.get("score", 0), errors="coerce").fillna(0).astype(int)
    df["controversiality"]= pd.to_numeric(df.get("controversiality", 0), errors="coerce").fillna(0).astype(int)

    # Drop empty/null subreddits
    df = df[df["subreddit"].str.len() > 0]
    # Drop duplicates within chunk
    df = df.drop_duplicates(subset=["body"])

    return df


def get_connection():
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://moderator:password@localhost:5432/content_moderation"
    )
    from urllib.parse import urlparse
    p = urlparse(db_url)
    return psycopg2.connect(
        host=p.hostname, port=p.port or 5432,
        user=p.username, password=p.password,
        dbname=p.path.lstrip("/")
    )


def bulk_insert_chunk(conn, df: pd.DataFrame):
    """
    Insert a cleaned chunk using PostgreSQL COPY for maximum throughput.
    ~100K rows/sec vs ~1K rows/sec for executemany.
    """
    buf = StringIO()
    for _, row in df.iterrows():
        # Escape backslashes for Postgres COPY, then remove tabs/newlines
        clean_body = row["body"].replace("\\", "\\\\").replace("\t", " ").replace("\n", " ").replace("\r", " ")
        line = "\t".join([
            clean_body,
            "comment",
            row["subreddit"],
            str(row["score"]),
            str(row["controversiality"]),
        ])
        buf.write(line + "\n")
    buf.seek(0)

    cursor = conn.cursor()
    cursor.copy_from(
        buf,
        "content",
        columns=("text", "content_type", "subreddit", "score", "controversiality"),
        sep="\t",
        null=""
    )
    conn.commit()
    cursor.close()


def load_csv(csv_path: str, sample: int | None = None):
    path = Path(csv_path)
    if not path.exists():
        logger.error(f"CSV not found: {csv_path}")
        sys.exit(1)

    logger.info(f"Loading: {path.name}  (chunk={CHUNK_SIZE:,})")
    if sample:
        logger.info(f"  Sample mode: first {sample:,} rows only")

    conn          = get_connection()
    total_read    = 0
    total_inserted= 0
    total_dropped = 0
    start         = time.time()

    try:
        reader = pd.read_csv(
            path,
            chunksize=CHUNK_SIZE,
            usecols=lambda c: c in {"subreddit", "body", "score", "controversiality"},
            on_bad_lines="skip",
            dtype=str,             # read everything as str first; cast later
            low_memory=False,
        )

        for i, chunk in enumerate(reader, start=1):
            chunk_start = len(chunk)
            total_read += chunk_start

            cleaned = clean_chunk(chunk)
            inserted = len(cleaned)
            dropped  = chunk_start - inserted

            total_inserted += inserted
            total_dropped  += dropped

            if inserted > 0:
                bulk_insert_chunk(conn, cleaned)

            elapsed = time.time() - start
            rate    = total_inserted / elapsed
            logger.info(
                f"  Chunk {i:4d} | +{inserted:,} rows | "
                f"total={total_inserted:,} | dropped={total_dropped:,} | "
                f"{rate:,.0f} rows/sec"
            )

            if sample and total_read >= sample:
                logger.info(f"  Sample limit reached ({sample:,}). Stopping.")
                break

    except Exception as e:
        conn.rollback()
        logger.error(f"Error: {e}")
        raise
    finally:
        conn.close()

    elapsed = time.time() - start
    logger.info(
        f"\n✅ Done in {elapsed:.1f}s — "
        f"Inserted: {total_inserted:,} | Dropped: {total_dropped:,} | "
        f"Drop rate: {100*total_dropped/(total_read or 1):.1f}%"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk load Reddit CSV into PostgreSQL")
    parser.add_argument("--csv",    required=True, help="Path to reddit CSV file")
    parser.add_argument("--sample", type=int, default=None,
                        help="Load only first N rows (for testing)")
    args = parser.parse_args()
    load_csv(args.csv, args.sample)
