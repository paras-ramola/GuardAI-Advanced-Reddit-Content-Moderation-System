
import re
import string
import logging
import nltk
from nltk.stem.porter import PorterStemmer
from nltk.corpus import stopwords

logger = logging.getLogger(__name__)

# Download required NLTK data once
for resource in ["stopwords", "punkt"]:
    try:
        nltk.data.find(f"tokenizers/{resource}" if resource == "punkt" else f"corpora/{resource}")
    except LookupError:
        nltk.download(resource, quiet=True)

STEMMER   = PorterStemmer()
STOPWORDS = set(stopwords.words("english"))

# Common toxic/hate keywords for fast highlighting (fallback when no attention weights)
TOXIC_KEYWORDS = {
    "hate", "idiot", "stupid", "dumb", "racist", "sexist", "kill", "die",
    "trash", "garbage", "worthless", "disgusting", "freak", "loser", "moron",
    "terrorist", "violent", "attack", "threat", "slur", "abuse",
}


class TextPreprocessor:
    """
    Reusable preprocessing pipeline.

    Two modes:
    - clean_for_training (str -> str): full cleaning + stemming (for TF-IDF / DistilBERT training)
    - clean_for_display (str -> str): light cleaning without stemming (keep readable for UI)
    """

    @staticmethod
    def _remove_pattern(text: str, pattern: str) -> str:
        matches = re.findall(pattern, text)
        for match in matches:
            text = re.sub(re.escape(match), "", text)
        return text

    def clean_for_training(self, text: str) -> str:
        """Full pipeline — strips handles, URLs, punctuation, short words, stems."""
        if not isinstance(text, str):
            return ""

        # 1. Remove @handles
        text = self._remove_pattern(text, r"@[\w]*")

        # 2. Remove URLs
        text = re.sub(r"http\S+|www\S+", "", text)

        # 3. Remove special chars & digits (keep letters and #)
        text = re.sub(r"[^a-zA-Z#\s]", " ", text)

        # 4. Lowercase
        text = text.lower()

        # 5. Remove short words (<= 3 chars) but keep hashtag content
        tokens = [w for w in text.split() if len(w) > 3]

        # 6. Stem
        tokens = [STEMMER.stem(w) for w in tokens]

        return " ".join(tokens)

    def clean_for_display(self, text: str) -> str:
        """Light cleaning — remove handles/URLs but preserve readable words."""
        if not isinstance(text, str):
            return ""
        text = self._remove_pattern(text, r"@[\w]*")
        text = re.sub(r"http\S+|www\S+", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def extract_toxic_words(self, text: str) -> list[str]:
        """Return a list of words that match the toxic keyword list."""
        lowered = text.lower().split()
        return [w.strip(string.punctuation) for w in lowered
                if w.strip(string.punctuation) in TOXIC_KEYWORDS]
