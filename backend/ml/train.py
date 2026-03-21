"""
ML training script — Exclusive DistilBERT fine-tuning approach
Run: python -m ml.train
"""
import os
import sys
import json
import logging
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, accuracy_score, roc_auc_score
from dotenv import load_dotenv

import torch
from transformers import (
    DistilBertTokenizerFast, DistilBertForSequenceClassification,
    Trainer, TrainingArguments, EarlyStoppingCallback
)
from torch.utils.data import Dataset

warnings.filterwarnings("ignore")
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# ─── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"
DATA_PATH     = BASE_DIR.parent.parent / "Twitter Sentiments.csv"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

# ─── Preprocessing ─────────────────────────────────────────────────────────────
from ml.preprocessor import TextPreprocessor
preprocessor = TextPreprocessor()


def load_and_prepare_data():
    logger.info(f"Loading dataset from: {DATA_PATH}")
    df = pd.read_csv(DATA_PATH)
    logger.info(f"  Rows: {len(df)}, Columns: {list(df.columns)}")
    logger.info(f"  Label distribution:\n{df['label'].value_counts().to_string()}")

    df["clean_text"] = df["tweet"].apply(preprocessor.clean_for_training)
    df = df[df["clean_text"].str.len() > 0]         # drop empty strings

    X_train, X_test, y_train, y_test = train_test_split(
        df["clean_text"], df["label"],
        test_size=0.20, random_state=42, stratify=df["label"]
    )
    logger.info(f"  Train: {len(X_train)}, Test: {len(X_test)}")
    return X_train, X_test, y_train, y_test


# ─── DistilBERT Fine-tuning ───────────────────────────────────────────
def train_distilbert(X_train, X_test, y_train, y_test):
    """Fine-tune DistilBERT on the training set and save the model."""
    logger.info("─── DistilBERT fine-tuning ───")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu" and torch.backends.mps.is_available():
        device = "mps"
    logger.info(f"  Device: {device}")

    MODEL_NAME = "distilbert-base-uncased"
    tokenizer  = DistilBertTokenizerFast.from_pretrained(MODEL_NAME)

    class TweetDataset(Dataset):
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

    train_dataset = TweetDataset(X_train, y_train)
    test_dataset  = TweetDataset(X_test,  y_test)

    model = DistilBertForSequenceClassification.from_pretrained(
        MODEL_NAME, num_labels=2
    )

    training_args = TrainingArguments(
        output_dir=str(ARTIFACTS_DIR / "distilbert_checkpoints"),
        num_train_epochs=3,
        per_device_train_batch_size=32,
        per_device_eval_batch_size=64,
        learning_rate=2e-5,
        warmup_ratio=0.1,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        logging_steps=50,
        fp16=(device == "cuda"),
        report_to="none",
    )

    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        preds = np.argmax(logits, axis=1)
        proba = torch.softmax(torch.tensor(logits), dim=1).numpy()[:, 1]
        return {
            "f1":       round(f1_score(labels, preds), 4),
            "accuracy": round(accuracy_score(labels, preds), 4),
            "auc_roc":  round(roc_auc_score(labels, proba), 4),
        }

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=test_dataset,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
    )

    trainer.train()
    eval_result = trainer.evaluate()

    # Save model + tokenizer
    distilbert_path = ARTIFACTS_DIR / "distilbert"
    model.save_pretrained(distilbert_path)
    tokenizer.save_pretrained(distilbert_path)
    logger.info(f"  Saved DistilBERT model to: {distilbert_path}")

    metrics = {
        "model":    "DistilBERT (fine-tuned)",
        "f1":       eval_result.get("eval_f1", 0),
        "accuracy": eval_result.get("eval_accuracy", 0),
        "auc_roc":  eval_result.get("eval_auc_roc", 0),
    }
    logger.info(f"  DistilBERT metrics: {metrics}")
    return metrics


def main():
    X_train, X_test, y_train, y_test = load_and_prepare_data()

    distilbert_metrics = train_distilbert(X_train, X_test, y_train, y_test)

    # Save report
    report = {
        "distilbert": distilbert_metrics,
    }
    report_path = ARTIFACTS_DIR / "model_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"\nModel report saved to: {report_path}")
    logger.info("─── Training complete ───")


if __name__ == "__main__":
    main()

