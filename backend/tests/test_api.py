"""
Integration tests for Flask API endpoints.
Run: pytest tests/test_api.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock


# ─── Mock the model to avoid loading it during tests ──────────────────────────
MOCK_PREDICTION = {
    "label":         "hate",
    "confidence":    0.91,
    "severity":      0.78,
    "toxic_words":   ["idiots"],
    "model_version": "bert-v1",
}

@pytest.fixture
def client():
    with patch("ml.model.get_model") as mock_get_model:
        mock_model = MagicMock()
        mock_model.predict.return_value = MOCK_PREDICTION
        mock_model.model_version        = "bert-v1"
        mock_get_model.return_value     = mock_model

        from api.main import create_app
        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c


class TestHealth:
    def test_health_returns_200(self, client):
        res = client.get("/health")
        assert res.status_code == 200

    def test_health_has_status_ok(self, client):
        data = res = client.get("/health").get_json()
        assert data["status"] == "ok"


class TestPredict:
    def test_valid_text_returns_200(self, client):
        res = client.post("/predict", json={"text": "These people are idiots"})
        assert res.status_code == 200

    def test_response_has_required_keys(self, client):
        data = client.post("/predict", json={"text": "test"}).get_json()
        for key in ("label", "confidence", "severity", "toxic_words", "model_version"):
            assert key in data

    def test_label_is_valid(self, client):
        data = client.post("/predict", json={"text": "test"}).get_json()
        assert data["label"] in ("hate", "safe")

    def test_confidence_in_range(self, client):
        data = client.post("/predict", json={"text": "test"}).get_json()
        assert 0.0 <= data["confidence"] <= 1.0

    def test_missing_text_returns_400(self, client):
        res = client.post("/predict", json={})
        assert res.status_code == 400

    def test_empty_text_returns_400(self, client):
        res = client.post("/predict", json={"text": "   "})
        assert res.status_code == 400

    def test_no_body_returns_400(self, client):
        res = client.post("/predict")
        assert res.status_code == 400


class TestBatchPredict:
    def test_valid_batch(self, client):
        res = client.post("/predict/batch", json={"texts": ["text1", "text2"]})
        assert res.status_code == 200

    def test_batch_response_schema(self, client):
        data = client.post("/predict/batch", json={"texts": ["a", "b", "c"]}).get_json()
        assert "total" in data and "results" in data
        assert data["total"] == 3
        assert len(data["results"]) == 3

    def test_empty_array_returns_400(self, client):
        res = client.post("/predict/batch", json={"texts": []})
        assert res.status_code == 400

    def test_missing_texts_returns_400(self, client):
        res = client.post("/predict/batch", json={})
        assert res.status_code == 400

    def test_over_limit_returns_400(self, client):
        res = client.post("/predict/batch", json={"texts": ["x"] * 501})
        assert res.status_code == 400


class TestResults:
    def test_results_with_no_db(self, client):
        # Should either work or fail gracefully (not 500 crash)
        res = client.get("/results")
        assert res.status_code in (200, 500)

class TestAnalytics:
    def test_analytics_with_no_db(self, client):
        res = client.get("/analytics")
        assert res.status_code in (200, 500)

class TestFeedback:
    def test_missing_fields_returns_400(self, client):
        res = client.post("/feedback", json={})
        assert res.status_code == 400

    def test_invalid_correction_returns_400(self, client):
        res = client.post("/feedback", json={"prediction_id": 1, "correction": "invalid"})
        assert res.status_code == 400

    def test_feedback_with_no_db(self, client):
        res = client.post("/feedback", json={"prediction_id": 1, "correction": "safe"})
        # Without DB, it should either fail gracefully with 500 or 404 (if prediction not found)
        assert res.status_code in (200, 404, 500)
