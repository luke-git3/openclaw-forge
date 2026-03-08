"""
embedder.py — TF-IDF semantic search engine for Mnemosyne.

Why TF-IDF instead of vector embeddings?
  - Zero dependency on external APIs (no OpenAI embeddings endpoint needed)
  - Runs fully offline — perfect for demo/portfolio contexts
  - Surprisingly effective for factual memory retrieval (not much metaphor in user prefs)
  - Production upgrade path: swap compute_similarity() for sentence-transformers
    or OpenAI text-embedding-3-small — the interface stays identical.

Architecture:
  - MemoryIndex builds a TF-IDF matrix from all stored memories
  - search() returns top-k memories ranked by cosine similarity + importance boost
  - Index is rebuilt on demand (cheap at <1000 memories; add Redis cache for scale)
"""

import math
import re
from collections import Counter
from typing import Optional


# ─── Text preprocessing ───────────────────────────────────────────────────────

STOPWORDS = {
    "a", "an", "the", "is", "it", "in", "on", "at", "to", "for", "of",
    "and", "or", "but", "not", "with", "as", "be", "was", "are", "were",
    "has", "have", "had", "this", "that", "i", "you", "he", "she", "we",
    "they", "my", "your", "his", "her", "its", "our", "do", "does", "did",
    "will", "would", "can", "could", "should", "may", "might", "shall",
    "from", "by", "up", "out", "so", "if", "me", "him", "us", "them",
}


def tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, remove stopwords, return token list."""
    text = text.lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


# ─── TF-IDF implementation ────────────────────────────────────────────────────

class MemoryIndex:
    """
    Lightweight TF-IDF index over a list of memory dicts.

    Usage:
        index = MemoryIndex(memories)
        results = index.search("user prefers dark theme", top_k=5)
    """

    def __init__(self, memories: list[dict]):
        self.memories = memories
        self._build(memories)

    def _build(self, memories: list[dict]):
        """Compute TF-IDF vectors for all documents."""
        n = len(memories)
        if n == 0:
            self._vectors: list[dict[str, float]] = []
            self._idf: dict[str, float] = {}
            return

        # Tokenize each document
        tokenized = [tokenize(m["content"]) for m in memories]

        # Document frequency for IDF
        df: Counter = Counter()
        for tokens in tokenized:
            df.update(set(tokens))  # count docs containing each term (not occurrences)

        # IDF = log((N + 1) / (df + 1)) + 1  (smoothed, sklearn-style)
        self._idf = {
            term: math.log((n + 1) / (count + 1)) + 1
            for term, count in df.items()
        }

        # TF-IDF vectors as sparse dicts (memory-efficient for large corpora)
        self._vectors = []
        for tokens in tokenized:
            tf: Counter = Counter(tokens)
            doc_len = len(tokens) or 1
            vec = {
                term: (count / doc_len) * self._idf.get(term, 1.0)
                for term, count in tf.items()
            }
            # L2 normalize so cosine sim = dot product
            norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
            self._vectors.append({t: v / norm for t, v in vec.items()})

    def _query_vector(self, query: str) -> dict[str, float]:
        """Compute normalized TF-IDF vector for the search query."""
        tokens = tokenize(query)
        tf: Counter = Counter(tokens)
        doc_len = len(tokens) or 1
        vec = {
            term: (count / doc_len) * self._idf.get(term, 1.0)
            for term, count in tf.items()
            if term in self._idf  # only known terms contribute
        }
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    def _cosine(self, vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
        """Dot product of two normalized sparse vectors = cosine similarity."""
        return sum(vec_a.get(t, 0.0) * v for t, v in vec_b.items())

    def search(
        self,
        query: str,
        top_k: int = 5,
        tag_filter: Optional[str] = None,
        min_score: float = 0.01,
    ) -> list[dict]:
        """
        Return top-k memories ranked by combined score:
            score = cosine_similarity * 0.7 + importance_boost * 0.3

        Args:
            query:      Natural language search query
            top_k:      Max results to return
            tag_filter: Restrict to memories with this tag
            min_score:  Minimum combined score threshold (filters noise)

        Returns:
            List of memory dicts, each augmented with '_score' and '_rank'.
        """
        if not self.memories:
            return []

        qvec = self._query_vector(query)
        results = []

        for i, memory in enumerate(self.memories):
            # Tag filter
            if tag_filter and tag_filter not in memory.get("tags", []):
                continue

            # Cosine similarity [0, 1]
            cos_sim = self._cosine(qvec, self._vectors[i])

            # Importance boost: importance is 1-10, normalized to [0, 1]
            importance_boost = (memory.get("importance", 5) - 1) / 9.0

            # Recency boost: small bonus for recently accessed memories
            # (access_count normalized — caps at 10 to avoid domination)
            recency_boost = min(memory.get("access_count", 0), 10) / 100.0

            # Combined score
            score = cos_sim * 0.7 + importance_boost * 0.25 + recency_boost * 0.05

            if score >= min_score:
                results.append({**memory, "_score": round(score, 4)})

        # Sort descending by score, return top_k
        results.sort(key=lambda x: x["_score"], reverse=True)
        for rank, r in enumerate(results[:top_k], start=1):
            r["_rank"] = rank

        return results[:top_k]


# ─── Upgrade path documentation ───────────────────────────────────────────────
#
# To swap in sentence-transformers (production quality embeddings):
#
#   from sentence_transformers import SentenceTransformer
#   import numpy as np
#
#   model = SentenceTransformer("all-MiniLM-L6-v2")  # 22MB, runs offline
#
#   class ProductionMemoryIndex:
#       def __init__(self, memories):
#           self.memories = memories
#           contents = [m["content"] for m in memories]
#           self._embeddings = model.encode(contents, normalize_embeddings=True)
#
#       def search(self, query, top_k=5, ...):
#           qvec = model.encode([query], normalize_embeddings=True)[0]
#           scores = self._embeddings @ qvec  # batch cosine via matmul
#           ...
#
# Interface is identical. Drop-in replacement. 🔁
