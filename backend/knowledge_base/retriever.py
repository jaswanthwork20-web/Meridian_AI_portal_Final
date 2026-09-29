"""
Knowledge Base Hybrid Retriever
Provides unified hybrid search combining FAISS dense semantic embeddings
and BM25 lexical keyword matching with configurable weighting and confidence scoring.
"""
import os
import re
import json
import pickle
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
CANDIDATE_K = 10
TOP_K = 5
DENSE_WEIGHT = 0.65
LEXICAL_WEIGHT = 0.35
CONFIDENCE_THRESHOLD = 0.45

class HybridRetriever:
    _instance = None

    def __init__(self, data_dir: str = None):
        if not data_dir:
            base = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(base, "data")
            if not os.path.exists(os.path.join(data_dir, "knowledge.index")):
                # Fallback to root directory if present
                root_dir = os.path.dirname(base)
                if os.path.exists(os.path.join(root_dir, "knowledge.index")):
                    data_dir = root_dir

        self.data_dir = data_dir
        self.model = SentenceTransformer(MODEL_NAME)

        index_p = os.path.join(data_dir, "knowledge.index")
        meta_p = os.path.join(data_dir, "knowledge_meta.json")
        bm25_p = os.path.join(data_dir, "bm25_index.pkl")

        if os.path.exists(index_p):
            self.index = faiss.read_index(index_p)
        else:
            self.index = None

        if os.path.exists(meta_p):
            with open(meta_p, "r", encoding="utf-8") as f:
                self.meta = json.load(f)
        else:
            self.meta = []

        if os.path.exists(bm25_p):
            with open(bm25_p, "rb") as f:
                self.bm25 = pickle.load(f)["bm25"]
        else:
            self.bm25 = None

    @classmethod
    def get_instance(cls, data_dir: str = None):
        if cls._instance is None:
            cls._instance = cls(data_dir)
        return cls._instance

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r'\w+', text.lower())

    def dense_search(self, query: str, top_k: int = CANDIDATE_K) -> list[tuple[int, float]]:
        if not self.index or self.index.ntotal == 0:
            return []
        vec = self.model.encode([query], convert_to_numpy=True)
        faiss.normalize_L2(vec)
        scores, indices = self.index.search(vec, top_k)
        return [(int(idx), float(score)) for idx, score in zip(indices[0], scores[0]) if idx != -1]

    def lexical_search(self, query: str, top_k: int = CANDIDATE_K) -> list[tuple[int, float]]:
        if not self.bm25:
            return []
        scores = self.bm25.get_scores(self._tokenize(query))
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
        max_score = ranked[0][1] if ranked and ranked[0][1] > 0 else 1.0
        return [(idx, float(score / max_score)) for idx, score in ranked if score > 0]

    def search(self, query: str, top_k: int = TOP_K) -> list[dict]:
        """
        Hybrid search combining Dense Cosine Similarity + BM25 Lexical Score.
        Returns top ranked documents with structured fields: title, url, text, score.
        """
        dense_results = dict(self.dense_search(query))
        lexical_results = dict(self.lexical_search(query))

        all_candidates = set(dense_results.keys()) | set(lexical_results.keys())
        scored = []

        for idx in all_candidates:
            d_score = dense_results.get(idx, 0.0)
            l_score = lexical_results.get(idx, 0.0)
            hybrid_score = (d_score * DENSE_WEIGHT) + (l_score * LEXICAL_WEIGHT)
            scored.append((idx, hybrid_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        top_matches = scored[:top_k]

        results = []
        for idx, score in top_matches:
            if idx < len(self.meta):
                chunk = self.meta[idx]
                results.append({
                    "title": chunk.get("title", "Confluence Knowledge Base"),
                    "url": chunk.get("url", "https://agnishpaul2002.atlassian.net/wiki/spaces/SELFHELP"),
                    "text": chunk.get("text", ""),
                    "score": round(score, 4)
                })
        return results

    def is_escalation_needed(self, results: list[dict]) -> tuple[bool, float]:
        top_score = results[0]["score"] if results else 0.0
        escalate = (not results) or (top_score < CONFIDENCE_THRESHOLD)
        return escalate, top_score
