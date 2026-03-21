"""
ML retraining script — Active Learning pipeline
Run: python -m ml.retrain
"""
import os
import sys
import logging
import warnings
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

import torch
from transformers import (
    DistilBertTokenizerFast, DistilBertForSequenceClassification,
    Trainer, TrainingArguments
)
from torch.utils.data import Dataset

from ml.preprocessor import TextPreprocessor

warnings.filterwarnings("ignore")
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR      = Path(__file__).parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"
DISTILBERT_PATH = ARTIFACTS_DIR / "distilbert"

preprocessor = TextPreprocessor()

def fetch_feedback_data():
    """Fetch all rows from user_feedback where original_label != corrected_label."""
    from db.database import get_engine, get_session_factory, UserFeedback
    
    engine = get_engine()
    Session = get_session_factory(engine)
    db = Session()
    try:
        # Query mismatched feedback
        feedbacks = db.query(UserFeedback).filter(
            UserFeedback.original_label != UserFeedback.corrected_label
        ).all()
        
        data = []
        for fb in feedbacks:
            # Map labels to integers (0 = safe, 1 = hate to match train.py)
            label_int = 1 if fb.corrected_label == "hate" else 0
            # Clean text for training
            clean_text = preprocessor.clean_for_training(fb.text)
            if clean_text:
                data.append({"text": clean_text, "label": label_int})
                
        return pd.DataFrame(data)
    finally:
        db.close()


def retrain_model(df):
    if df.empty:
        logger.info("No new corrections found. Skipping retraining.")
        return

    logger.info(f"Retraining on {len(df)} feedback examples...")
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu" and torch.backends.mps.is_available():
        device = "mps"
    logger.info(f"Device: {device}")

    if not DISTILBERT_PATH.exists():
        logger.error(f"Active model not found at {DISTILBERT_PATH}!")
        sys.exit(1)

    tokenizer = DistilBertTokenizerFast.from_pretrained(str(DISTILBERT_PATH))

    class FeedbackDataset(Dataset):
        def __init__(self, texts, labels):
            self.encodings = tokenizer(
                list(texts), truncation=True, padding=True, max_length=128
            )
            self.labels = list(labels)

        def __len__(self):
            return len(self.labels)

        def __getitem__(self, idx):
            item = {k: torch.tensor(v[idx]) for k, v in self.encodings.items()}
            item["labels"] = torch.tensor(self.labels[idx])
            return item

    train_dataset = FeedbackDataset(df["text"], df["label"])

    model = DistilBertForSequenceClassification.from_pretrained(
        str(DISTILBERT_PATH), num_labels=2
    )

    training_args = TrainingArguments(
        output_dir=str(ARTIFACTS_DIR / "retrain_checkpoints"),
        num_train_epochs=1,
        per_device_train_batch_size=16,
        learning_rate=1e-5, # lower learning rate for fine-tuning on feedback
        weight_decay=0.01,
        save_strategy="no", # only save at the end
        fp16=(device == "cuda"),
        report_to="none",
        logging_steps=10
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
    )

    trainer.train()

    # Save updated weights
    model.save_pretrained(str(DISTILBERT_PATH))
    tokenizer.save_pretrained(str(DISTILBERT_PATH))
    logger.info("✅ Retraining complete. Updated weights saved.")


def main():
    df = fetch_feedback_data()
    retrain_model(df)


if __name__ == "__main__":
    main()
