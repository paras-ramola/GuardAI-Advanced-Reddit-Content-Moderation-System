"""
SQLAlchemy ORM models — v2 (offline Reddit dataset, BIGSERIAL IDs).
"""
import os
from sqlalchemy import (
    create_engine, Column, BigInteger, Integer, String, Float,
    Boolean, Text, ARRAY, TIMESTAMP, ForeignKey, text as sa_text, FetchedValue
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

Base = declarative_base()


class Content(Base):
    __tablename__ = "content"

    id               = Column(BigInteger, primary_key=True, autoincrement=True)
    text             = Column(Text, nullable=False)
    content_type     = Column(String(20), nullable=False, default="comment")
    subreddit        = Column(String(100), nullable=False)
    score            = Column(Integer, default=0)
    controversiality = Column(Integer, default=0)
    reddit_id        = Column(String(50), nullable=True)
    author           = Column(String(100), nullable=True)
    created_at       = Column(TIMESTAMP(timezone=True), server_default=sa_text("NOW()"))

    predictions = relationship("Prediction", back_populates="content",
                               cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id":               self.id,
            "text":             self.text,
            "content_type":     self.content_type,
            "subreddit":        self.subreddit,
            "score":            self.score,
            "controversiality": self.controversiality,
            "created_at":       self.created_at.isoformat() if self.created_at else None,
        }


class Prediction(Base):
    __tablename__ = "predictions"

    id                = Column(BigInteger, primary_key=True, autoincrement=True)
    content_id        = Column(BigInteger, ForeignKey("content.id", ondelete="CASCADE"), nullable=False)
    label             = Column(String(20), nullable=False)
    confidence        = Column(Float, nullable=False)
    severity          = Column(Float, nullable=False)
    toxic_words       = Column(ARRAY(Text), nullable=True)
    model_version     = Column(String(50), nullable=False, default="bert-v1")
    is_low_confidence = Column(Boolean, server_default=FetchedValue())
    created_at        = Column(TIMESTAMP(timezone=True), server_default=sa_text("NOW()"))

    content = relationship("Content", back_populates="predictions")

    def to_dict(self):
        return {
            "id":               self.id,
            "content_id":       self.content_id,
            "label":            self.label,
            "confidence":       round(self.confidence, 4),
            "severity":         round(self.severity, 4),
            "toxic_words":      self.toxic_words or [],
            "model_version":    self.model_version,
            "is_low_confidence": self.is_low_confidence,
            "created_at":       self.created_at.isoformat() if self.created_at else None,
        }


class AnalyticsCache(Base):
    __tablename__ = "analytics_cache"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    subreddit       = Column(String(100), nullable=False)
    total_analyzed  = Column(Integer, nullable=False)
    hate_count      = Column(Integer, nullable=False)
    hate_percentage = Column(Float, nullable=False)
    avg_severity    = Column(Float, nullable=False)
    computed_at     = Column(TIMESTAMP(timezone=True), server_default=sa_text("NOW()"))


class UserFeedback(Base):
    __tablename__ = "user_feedback"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    prediction_id   = Column(BigInteger, ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False)
    text            = Column(Text, nullable=False)
    original_label  = Column(String(20), nullable=False)
    corrected_label = Column(String(20), nullable=False)
    model_version   = Column(String(50), nullable=False)
    created_at      = Column(TIMESTAMP(timezone=True), server_default=sa_text("NOW()"))


# ─── Engine & Session ──────────────────────────────────────────────────────────
def get_engine():
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://moderator:password@localhost:5432/content_moderation"
    )
    return create_engine(
        db_url,
        poolclass=QueuePool,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=False,
    )


def get_session_factory(engine=None):
    if engine is None:
        engine = get_engine()
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


_engine = None
_SessionLocal = None


def get_db():
    global _engine, _SessionLocal
    if _engine is None:
        _engine = get_engine()
        _SessionLocal = get_session_factory(_engine)
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
