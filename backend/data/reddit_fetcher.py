"""
DB-based Reddit content fetcher (offline mode).
Queries the pre-loaded PostgreSQL content table instead of calling the Reddit API.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RedditDBFetcher:
    """
    Fetches Reddit content from the local PostgreSQL database.
    Replaces the PRAW live-API fetcher when Reddit credentials aren't available.
    """

    def __init__(self, session):
        self.session = session

    def fetch_top_comments(
        self,
        subreddit: str,
        limit: int = 50,
        min_score: Optional[int] = None,
        filter_controversial: bool = False,
    ) -> list[dict]:
        """
        Fetch top-scoring comments from a subreddit.

        Args:
            subreddit:              subreddit name (case-insensitive)
            limit:                  max number of rows to return (default 50)
            min_score:              only return comments with score >= this value
            filter_controversial:   if True, only return controversial=1 comments

        Returns:
            List of dicts: {text, subreddit, score, controversiality, content_type, id}
        """
        from db.database import Content
        from sqlalchemy import desc

        subreddit = subreddit.strip().lower().lstrip("r/")

        query = (
            self.session.query(Content)
            .filter(Content.subreddit == subreddit)
            .order_by(desc(Content.score))    # top-scored first
        )

        if min_score is not None:
            query = query.filter(Content.score >= min_score)

        if filter_controversial:
            query = query.filter(Content.controversiality == 1)

        rows = query.limit(limit).all()

        if not rows:
            logger.warning(f"No content found for r/{subreddit}")

        logger.info(f"Fetched {len(rows)} rows from r/{subreddit}")

        return [
            {
                "id":               r.id,
                "text":             r.text,
                "subreddit":        r.subreddit,
                "score":            r.score,
                "controversiality": r.controversiality,
                "content_type":     r.content_type,
            }
            for r in rows
        ]

    def list_available_subreddits(self, limit: int = 50) -> list[dict]:
        """Return subreddits available in the DB with their comment counts."""
        from sqlalchemy import func
        from db.database import Content

        rows = (
            self.session.query(
                Content.subreddit,
                func.count(Content.id).label("count"),
                func.avg(Content.score).label("avg_score"),
            )
            .group_by(Content.subreddit)
            .order_by(func.count(Content.id).desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "subreddit": r.subreddit,
                "count":     r.count,
                "avg_score": round(float(r.avg_score or 0), 1),
            }
            for r in rows
        ]
