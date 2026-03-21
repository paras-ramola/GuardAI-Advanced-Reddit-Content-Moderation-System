"""
Flask route blueprints — v2 (offline Reddit dataset, no PRAW).

All Reddit content is served from PostgreSQL, pre-loaded from the 1.9M row CSV.
"""
import logging
from functools import lru_cache
from flask import Blueprint, jsonify, request

logger = logging.getLogger("api.routes")
bp = Blueprint("api", __name__)


# ─── Helpers ───────────────────────────────────────────────────────────────────
def get_model():
    from ml.model import get_model as _get
    return _get()


def get_db_session():
    from db.database import get_engine, get_session_factory
    engine = get_engine()
    return get_session_factory(engine)()


# ─── Health ────────────────────────────────────────────────────────────────────
@bp.route("/health")
def health():
    model = get_model()
    return jsonify({
        "status":        "ok",
        "model_version": model.model_version,
        "data_source":   "offline_postgresql",
    }), 200


# ─── Single Prediction ─────────────────────────────────────────────────────────
@bp.route("/predict", methods=["POST"])
def predict():
    """
    Classify a single piece of text.
    Body: { "text": "..." }
    """
    body = request.get_json(silent=True)
    if not body or "text" not in body:
        return jsonify({"error": "Request body must contain a 'text' field"}), 400
    text = str(body["text"]).strip()
    if not text:
        return jsonify({"error": "'text' must not be empty"}), 400

    result = get_model().predict(text)
    result["input_text"] = text
    return jsonify(result), 200


# ─── Batch Prediction ──────────────────────────────────────────────────────────
@bp.route("/predict/batch", methods=["POST"])
def predict_batch():
    """
    Classify up to 500 texts at once.
    Body: { "texts": ["...", "..."] }
    """
    body = request.get_json(silent=True)
    if not body or "texts" not in body:
        return jsonify({"error": "Request body must contain a 'texts' array"}), 400
    texts = body["texts"]
    if not isinstance(texts, list) or len(texts) == 0:
        return jsonify({"error": "'texts' must be a non-empty array"}), 400
    if len(texts) > 500:
        return jsonify({"error": "Maximum 500 texts per batch"}), 400

    model   = get_model()
    results = [{"input_text": t, **model.predict(t)} for t in texts]
    hate    = sum(1 for r in results if r["label"] == "hate")
    return jsonify({
        "total":      len(results),
        "hate_count": hate,
        "hate_pct":   round(100 * hate / len(results), 1),
        "results":    results,
    }), 200


# ─── Subreddit Analysis (offline DB) ───────────────────────────────────────────
@bp.route("/analyze/reddit")
def analyze_reddit():
    """
    Fetch top comments for a subreddit from PostgreSQL, run the ML model,
    store predictions, return results + summary analytics.

    Query params:
        subreddit              (str, required)
        limit                  (int, default 50, max 200)
        min_score              (int, optional) — only fetch comments with score >= N
        controversial_only     (bool, optional) — only fetch controversiality=1
    """
    subreddit = request.args.get("subreddit", "").strip().lower().lstrip("r/")
    if not subreddit:
        return jsonify({"error": "'subreddit' query parameter is required"}), 400

    limit        = min(int(request.args.get("limit", 50)), 200)
    min_score    = request.args.get("min_score", type=int)
    controversial = request.args.get("controversial_only", "").lower() in ("1", "true", "yes")

    db = get_db_session()
    try:
        from data.reddit_fetcher import RedditDBFetcher
        fetcher = RedditDBFetcher(db)
        items   = fetcher.fetch_top_comments(
            subreddit,
            limit=limit,
            min_score=min_score,
            filter_controversial=controversial,
        )
    except Exception as e:
        db.close()
        logger.error(f"DB fetch error: {e}")
        return jsonify({
            "error": f"Could not fetch r/{subreddit} from database.",
            "hint":  "Make sure you've run: python -m data.load_reddit_csv --csv <path>"
        }), 404

    if not items:
        db.close()
        return jsonify({
            "error": f"No content found for r/{subreddit}",
            "hint":  "This subreddit may not be in the dataset. Try /subreddits to see available ones.",
        }), 404

    # ── Batch inference ──────────────────────────────────────────────────────
    model   = get_model()
    texts   = [item["text"] for item in items]
    # DistilBERT processes in batch for efficiency
    preds   = _batch_predict(model, texts, batch_size=32)

    # ── Store predictions ────────────────────────────────────────────────────
    results = []
    try:
        from db.database import Prediction
        predictions_objs = []
        for item, pred in zip(items, preds):
            prediction = Prediction(
                content_id    = item["id"],
                label         = pred["label"],
                confidence    = pred["confidence"],
                severity      = pred["severity"],
                toxic_words   = pred["toxic_words"] or [],
                model_version = pred["model_version"],
            )
            db.add(prediction)
            predictions_objs.append((item, pred, prediction))

        db.flush()  # assign DB IDs so we can return prediction_id to the frontend

        for item, original_pred, p_obj in predictions_objs:
            pred_dict = dict(original_pred)
            pred_dict["id"] = p_obj.id

            results.append({
                "text":             item["text"][:300],   # truncate for response size
                "subreddit":        item["subreddit"],
                "score":            item["score"],
                "controversiality": item["controversiality"],
                "content_type":     item["content_type"],
                "prediction":       pred_dict,
            })

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"DB write error: {e}")
        return jsonify({"error": "Database write failed", "detail": str(e)}), 500
    finally:
        db.close()

    # ── Analytics summary ────────────────────────────────────────────────────
    hate_items  = [r for r in results if r["prediction"]["label"] == "hate"]
    avg_severity = (
        round(sum(r["prediction"]["severity"] for r in hate_items) / len(hate_items), 3)
        if hate_items else 0.0
    )

    return jsonify({
        "subreddit":        f"r/{subreddit}",
        "total_analyzed":   len(results),
        "hate_count":       len(hate_items),
        "hate_pct":         round(100 * len(hate_items) / len(results), 1),
        "avg_severity":     avg_severity,
        "data_source":      "offline_postgresql",
        "results":          results,
    }), 200


# ─── Available Subreddits ───────────────────────────────────────────────────────
@bp.route("/subreddits")
def list_subreddits():
    """
    List all subreddits in the database with comment counts.
    Useful for the frontend to show autocomplete / suggestions.
    """
    limit = min(int(request.args.get("limit", 100)), 500)
    db    = get_db_session()
    try:
        from data.reddit_fetcher import RedditDBFetcher
        fetcher = RedditDBFetcher(db)
        subs    = fetcher.list_available_subreddits(limit=limit)
        return jsonify({"subreddits": subs, "total": len(subs)}), 200
    except Exception as e:
        logger.error(f"Subreddit list error: {e}")
        return jsonify({"error": "Failed to list subreddits"}), 500
    finally:
        db.close()


# ─── Stored Results (paginated) ─────────────────────────────────────────────────
@bp.route("/results")
def get_results():
    subreddit = request.args.get("subreddit", "").strip().lower()
    label     = request.args.get("label", "").strip().lower()
    page      = max(int(request.args.get("page", 1)), 1)
    per_page  = min(int(request.args.get("per_page", 20)), 100)

    db = get_db_session()
    try:
        from db.database import Content, Prediction
        from sqlalchemy.orm import joinedload

        query = (
            db.query(Prediction)
            .join(Content)
            .options(joinedload(Prediction.content))
        )
        if subreddit:
            query = query.filter(Content.subreddit == subreddit)
        if label in ("hate", "safe"):
            query = query.filter(Prediction.label == label)

        total  = query.count()
        items  = (query.order_by(Prediction.created_at.desc())
                       .offset((page - 1) * per_page).limit(per_page).all())

        results = []
        for p in items:
            row = p.to_dict()
            row["content"] = p.content.to_dict()
            results.append(row)

        return jsonify({
            "total":    total,
            "page":     page,
            "per_page": per_page,
            "pages":    max(1, (total + per_page - 1) // per_page),
            "results":  results,
        }), 200
    except Exception as e:
        logger.error(f"Results query error: {e}")
        return jsonify({"error": "Query failed", "detail": str(e)}), 500
    finally:
        db.close()


# ─── Analytics ──────────────────────────────────────────────────────────────────
@bp.route("/analytics")
def analytics():
    subreddit = request.args.get("subreddit", "").strip().lower()
    db        = get_db_session()
    try:
        from db.database import Content, Prediction
        from sqlalchemy import func, case

        base = db.query(Prediction).join(Content)
        if subreddit:
            base = base.filter(Content.subreddit == subreddit)

        total      = base.count()
        hate_count = base.filter(Prediction.label == "hate").count()
        avg_sev    = (db.query(func.avg(Prediction.severity))
                        .select_from(Prediction).join(Content))
        if subreddit:
            avg_sev = avg_sev.filter(Content.subreddit == subreddit)
        avg_sev  = float(avg_sev.scalar() or 0.0)
        low_conf = base.filter(Prediction.is_low_confidence == True).count()

        # Top subreddits breakdown
        sub_q = (
            db.query(
                Content.subreddit,
                func.count(Prediction.id).label("count"),
                func.sum(case((Prediction.label == "hate", 1), else_=0)).label("hate_count"),
                func.avg(Prediction.severity).label("avg_severity"),
            )
            .join(Content)
            .group_by(Content.subreddit)
            .order_by(func.count(Prediction.id).desc())
            .limit(10)
        )
        subreddit_breakdown = [
            {
                "subreddit":    r.subreddit,
                "total":        r.count,
                "hate_count":   r.hate_count or 0,
                "hate_pct":     round(100 * (r.hate_count or 0) / r.count, 1),
                "avg_severity": round(float(r.avg_severity or 0), 3),
            }
            for r in sub_q
        ]

        return jsonify({
            "total_analyzed":  total,
            "hate_count":      hate_count,
            "hate_percentage": round(100 * hate_count / total, 1) if total else 0.0,
            "safe_count":      total - hate_count,
            "avg_severity":    round(avg_sev, 3),
            "low_confidence":  low_conf,
            "subreddits":      subreddit_breakdown,
        }), 200
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        return jsonify({"error": "Analytics failed", "detail": str(e)}), 500
    finally:
        db.close()


# ─── Feedback Loop ──────────────────────────────────────────────────────────────
@bp.route("/feedback", methods=["POST"])
def feedback():
    """
    Log user feedback for a prediction.
    Body: {"prediction_id": <int>, "correction": "<string>"}
    """
    body = request.get_json(silent=True)
    if not body or "prediction_id" not in body or "correction" not in body:
        return jsonify({"error": "Missing 'prediction_id' or 'correction'"}), 400

    pred_id = body["prediction_id"]
    correction = str(body["correction"]).strip().lower()

    if correction not in ("safe", "hate"):
        return jsonify({"error": "Correction must be 'safe' or 'hate'"}), 400

    db = get_db_session()
    try:
        from db.database import Prediction, UserFeedback
        
        # Get the original prediction
        prediction = db.query(Prediction).filter(Prediction.id == pred_id).first()
        if not prediction:
            return jsonify({"error": "Prediction not found"}), 404

        # Verify it has content
        if not prediction.content:
            return jsonify({"error": "Content for prediction not found"}), 404

        # Create feedback record
        new_feedback = UserFeedback(
            prediction_id=pred_id,
            text=prediction.content.text,
            original_label=prediction.label,
            corrected_label=correction,
            model_version=prediction.model_version
        )
        db.add(new_feedback)
        db.commit()

        return jsonify({
            "status": "ok",
            "message": "Feedback recorded successfully"
        }), 200
    except Exception as e:
        db.rollback()
        logger.error(f"Feedback error: {e}")
        return jsonify({"error": "Failed to save feedback", "detail": str(e)}), 500
    finally:
        db.close()


# ─── Batch inference helper ────────────────────────────────────────────────────
def _batch_predict(model, texts: list[str], batch_size: int = 32) -> list[dict]:
    """
    Run inference in mini-batches for DistilBERT efficiency.
    """
    results = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i: i + batch_size]
        results.extend([model.predict(t) for t in batch])
    return results
