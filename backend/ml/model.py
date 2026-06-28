
import os
import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from ml.preprocessor import TextPreprocessor

load_dotenv()
logger = logging.getLogger(__name__)

ARTIFACTS_DIR  = Path(__file__).parent / "artifacts"
HATE_THRESHOLD = float(os.getenv("HATE_THRESHOLD", "0.3"))


class ContentModerationModel:
    """
    Inference interface for DistilBERT content moderation.
    """

    def __init__(self):
        self.preprocessor   = TextPreprocessor()
        self._bert_model    = None
        self._bert_tokenizer= None
        self.model_version  = "unloaded"
        self._device        = "cpu"

        self._load()

    # ─── Model Loading ─────────────────────────────────────────────────────────
    def _load(self):
        loaded = self._try_load_distilbert()
        if not loaded:
            logger.error("DistilBERT model not found. Please run: python -m ml.train")
            self.model_version = "not-found"

    def _try_load_distilbert(self) -> bool:
        distilbert_path = ARTIFACTS_DIR / "distilbert"
        if not distilbert_path.exists():
            return False
        try:
            from transformers import (
                DistilBertTokenizerFast,
                DistilBertForSequenceClassification,
            )
            import torch

            self._bert_tokenizer = DistilBertTokenizerFast.from_pretrained(str(distilbert_path))
            self._bert_model     = DistilBertForSequenceClassification.from_pretrained(
                str(distilbert_path)
            )
            self._bert_model.eval()
            self._device      = "cuda" if torch.cuda.is_available() else "cpu"
            if self._device == "cpu" and torch.backends.mps.is_available():
                self._device = "mps"
                
            self._bert_model  = self._bert_model.to(self._device)
            self.model_version = "bert-v1"
            logger.info(f"DistilBERT loaded on {self._device}")
            return True
        except Exception as e:
            logger.error(f"Failed to load DistilBERT: {e}")
            return False

    # ─── Inference ─────────────────────────────────────────────────────────────
    def predict(self, text: str) -> dict:
        """
        Predict hate/safe label for a single piece of text.

        Returns:
            {
                "label":         "hate" | "safe",
                "confidence":    float (0–1),
                "severity":      float (0–1),
                "toxic_words":   list[str],
                "model_version": str
            }
        """
        if not text or not text.strip():
            return self._empty_result()

        toxic_words = self.preprocessor.extract_toxic_words(text)

        if self._bert_model is None:
            return self._empty_result()
            
        return self._predict_bert(text, toxic_words)

    def predict_batch(self, texts: list[str]) -> list[dict]:
        """Predict a list of texts efficiently."""
        return [self.predict(t) for t in texts]

    def _predict_bert(self, text: str, toxic_words: list[str]) -> dict:
        import torch

        clean   = self.preprocessor.clean_for_display(text)
        inputs  = self._bert_tokenizer(
            clean, return_tensors="pt", truncation=True,
            padding=True, max_length=128
        )
        inputs  = {k: v.to(self._device) for k, v in inputs.items()}

        with torch.no_grad():
            logits = self._bert_model(**inputs).logits
            probs  = torch.softmax(logits, dim=1).cpu().numpy()[0]

        hate_prob  = float(probs[1])
        is_hate    = hate_prob >= HATE_THRESHOLD
        label      = "hate" if is_hate else "safe"
        confidence = hate_prob if is_hate else float(probs[0])
        severity   = self._compute_severity(hate_prob, is_hate)

        return {
            "label":         label,
            "confidence":    round(confidence, 4),
            "severity":      round(severity, 4),
            "toxic_words":   toxic_words,
            "model_version": self.model_version,
        }

    @staticmethod
    def _compute_severity(hate_prob: float, is_hate: bool) -> float:
        """Severity = calibrated hate probability (0 = safe, 1 = extreme hate)."""
        if is_hate:
            # Map [threshold, 1.0] → [0.3, 1.0]
            normalized = (hate_prob - HATE_THRESHOLD) / (1.0 - HATE_THRESHOLD)
            return round(min(max(normalized, 0.0), 1.0), 4)
        return round(hate_prob, 4)    # severity is the raw hate prob for safe items

    @staticmethod
    def _empty_result() -> dict:
        return {
            "label":         "safe",
            "confidence":    0.0,
            "severity":      0.0,
            "toxic_words":   [],
            "model_version": "n/a",
        }


# ─── Singleton ─────────────────────────────────────────────────────────────────
_model_instance: Optional[ContentModerationModel] = None


def get_model() -> ContentModerationModel:
    """Return the singleton model instance (lazy-loaded)."""
    global _model_instance
    if _model_instance is None:
        _model_instance = ContentModerationModel()
    return _model_instance
