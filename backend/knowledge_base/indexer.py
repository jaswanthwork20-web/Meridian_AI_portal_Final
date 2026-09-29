"""
Knowledge Base Indexer
Generates dense vector embeddings via SentenceTransformer (all-MiniLM-L6-v2) for FAISS
and BM25 tokenized lexical indexes.
"""
import os
import json
import pickle
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

MODEL_NAME = "all-MiniLM-L6-v2"

def build_faiss_index(chunks_path: str, index_output: str, meta_output: str):
    """Builds a FAISS IndexFlatIP (cosine similarity) from knowledge chunks."""
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    texts = [f"{c['title']}\n{c['text']}" for c in chunks]
    print(f"[Indexer] Embedding {len(texts)} chunks using {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=True)
    faiss.normalize_L2(embeddings)

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)

    faiss.write_index(index, index_output)
    with open(meta_output, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2)

    print(f"[Indexer] Saved FAISS index ({index.ntotal} vectors) -> {index_output}")

def build_bm25_index(chunks_path: str, bm25_output: str):
    """Builds a BM25Okapi lexical index from knowledge chunks."""
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    def tokenize(text):
        import re
        return re.findall(r'\w+', text.lower())

    corpus = [tokenize(f"{c['title']} {c['text']}") for c in chunks]
    bm25 = BM25Okapi(corpus)

    with open(bm25_output, "wb") as f:
        pickle.dump({"bm25": bm25, "chunks": chunks}, f)

    print(f"[Indexer] Saved BM25 index ({len(chunks)} documents) -> {bm25_output}")

def build_all(data_dir: str):
    chunks_p = os.path.join(data_dir, "knowledge_chunks.json")
    faiss_p = os.path.join(data_dir, "knowledge.index")
    meta_p = os.path.join(data_dir, "knowledge_meta.json")
    bm25_p = os.path.join(data_dir, "bm25_index.pkl")
    build_faiss_index(chunks_p, faiss_p, meta_p)
    build_bm25_index(chunks_p, bm25_p)

if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    build_all(os.path.join(base, "data"))
