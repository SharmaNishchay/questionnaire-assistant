"""
RAG Engine
- Embeddings : sentence-transformers (local, no API key needed)
- Generation : Groq API (free tier — llama-3.3-70b-versatile)
               Falls back to best-matching text snippet if no GROQ_API_KEY set.
"""

import os
import numpy as np
import faiss
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Lazy-load the embedding model so startup is not blocked
_embed_model = None

def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        print("⏳ Loading local embedding model (all-MiniLM-L6-v2)…")
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
        print("✓ Embedding model ready")
    return _embed_model


class RAGEngine:
    # all-MiniLM-L6-v2 outputs 384-dim vectors
    DIMENSION = 384

    def __init__(self):
        self.index = None
        self.chunks: List[str] = []
        self.metadata: List[Dict] = []

    # Embeddings
    def create_embedding(self, text: str) -> List[float]:
        model = _get_embed_model()
        vec = model.encode(text, normalize_embeddings=True)
        return vec.tolist()

    def create_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Encode a whole batch at once — much faster than one-by-one."""
        model = _get_embed_model()
        vecs = model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
        return vecs.tolist()

    # Text chunking
    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
        chunks = []
        start = 0
        while start < len(text):
            chunk = text[start:start + chunk_size]
            if chunk.strip():
                chunks.append(chunk)
            start += chunk_size - overlap
        return chunks

    # Index management
    def _ensure_index(self):
        if self.index is None:
            self.index = faiss.IndexFlatIP(self.DIMENSION)

    def build_index(self, documents: List[Dict]):
        all_chunks, all_metadata = [], []
        for doc in documents:
            for i, chunk in enumerate(self.chunk_text(doc["text"])):
                all_chunks.append(chunk)
                all_metadata.append({
                    "source": doc["source"],
                    "doc_id": doc.get("doc_id"),
                    "chunk_index": i,
                    "text": chunk,
                })
        if not all_chunks:
            return
        embeddings = np.array(self.create_embeddings_batch(all_chunks), dtype="float32")
        self.index = faiss.IndexFlatIP(self.DIMENSION)
        self.index.add(embeddings)
        self.chunks = all_chunks
        self.metadata = all_metadata

    def add_document(self, text: str, source: str, doc_id: int = None):
        chunks = self.chunk_text(text)
        if not chunks:
            return
        embeddings = np.array(self.create_embeddings_batch(chunks), dtype="float32")
        self._ensure_index()
        self.index.add(embeddings)
        for i, chunk in enumerate(chunks):
            self.chunks.append(chunk)
            self.metadata.append({
                "source": source,
                "doc_id": doc_id,
                "chunk_index": i,
                "text": chunk,
            })

    def remove_document(self, doc_id: int):
        remaining_chunks, remaining_metadata = [], []
        for chunk, meta in zip(self.chunks, self.metadata):
            if meta.get("doc_id") != doc_id:
                remaining_chunks.append(chunk)
                remaining_metadata.append(meta)
        self.chunks = remaining_chunks
        self.metadata = remaining_metadata
        if self.chunks:
            embeddings = np.array(self.create_embeddings_batch(self.chunks), dtype="float32")
            self.index = faiss.IndexFlatIP(self.DIMENSION)
            self.index.add(embeddings)
        else:
            self.index = None

    # Search
    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        if self.index is None or self.index.ntotal == 0:
            return []
        q_vec = np.array([self.create_embedding(query)], dtype="float32")
        scores, indices = self.index.search(q_vec, min(top_k, self.index.ntotal))
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < len(self.metadata):
                entry = self.metadata[idx].copy()
                entry["relevance_score"] = float(score)
                results.append(entry)
        return results

    # Generation  (Groq free tier)
    def _generate_with_groq(self, question: str, context: str) -> str:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        prompt = (
            "You are answering a vendor questionnaire based on the provided reference documents.\n\n"
            f"Question: {question}\n\n"
            f"Reference Context:\n{context}\n\n"
            "Instructions:\n"
            "1. Answer directly and concisely using ONLY the provided context.\n"
            "2. If the context lacks relevant information, say exactly: Not found in references.\n"
            "3. Be specific and professional.\n\n"
            "Answer:"
        )
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You answer questionnaires strictly from the given context."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=512,
        )
        return response.choices[0].message.content.strip()

    def generate_answer(self, question: str, context_chunks: List[Dict]) -> Dict:
        if not context_chunks:
            return {"answer": "Not found in references.", "citations": [], "confidence": 0.0}

        context = "\n\n".join(
            f"[Source: {c['source']}]\n{c['text']}" for c in context_chunks
        )
        avg_confidence = float(np.mean([c["relevance_score"] for c in context_chunks]))

        # Build deduplicated citations
        seen, citations = set(), []
        for chunk in context_chunks:
            if chunk["source"] not in seen:
                seen.add(chunk["source"])
                snippet = chunk["text"]
                citations.append({
                    "source": chunk["source"],
                    "snippet": snippet[:200] + "..." if len(snippet) > 200 else snippet,
                    "page": None,
                })
            if len(citations) >= 3:
                break

        # Try Groq first
        if GROQ_API_KEY:
            try:
                answer_text = self._generate_with_groq(question, context)
                return {"answer": answer_text, "citations": citations, "confidence": avg_confidence}
            except Exception as e:
                print(f"⚠ Groq error: {e} — falling back to snippet mode")

        # Fallback: return best matching snippet as-is
        best = context_chunks[0]["text"][:500]
        return {"answer": best, "citations": citations, "confidence": avg_confidence}

    def query(self, question: str) -> Dict:
        return self.generate_answer(question, self.search(question, top_k=3))


# Global singleton
rag_engine = RAGEngine()
