import json
from uuid import UUID

import numpy as np
from google import genai
from sqlmodel import Session, select

from app.config import get_settings
from app.models.highlight import Highlight


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    if not settings.gemini_api_key:
        return []
    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.embed_content(model="text-embedding-004", contents=texts)
    return [e.values for e in response.embeddings]


def backfill_embeddings(session: Session) -> dict[str, int | str]:
    settings = get_settings()
    if not settings.gemini_api_key:
        return {"processed": 0, "error": "No API key configured."}

    query = select(Highlight).where(Highlight.embedding.is_(None))
    highlights = session.exec(query).all()
    if not highlights:
        return {"processed": 0}

    batch_size = 100
    processed = 0
    for i in range(0, len(highlights), batch_size):
        batch = highlights[i : i + batch_size]
        texts = [h.content or h.note or " " for h in batch]
        texts = [t if t.strip() else " " for t in texts]

        try:
            embeddings = generate_embeddings(texts)
            for j, emb in enumerate(embeddings):
                batch[j].embedding = json.dumps(emb)
                session.add(batch[j])
            session.commit()
            processed += len(batch)
        except Exception as e:
            print("Embedding error:", e)
            break

    return {"processed": processed}


def get_related_highlights(session: Session, target_id: UUID, limit: int = 5) -> list[Highlight]:
    target = session.get(Highlight, target_id)
    if not target or not target.embedding:
        return []

    target_vec = np.array(json.loads(target.embedding))

    query = select(Highlight).where(Highlight.embedding.is_not(None), Highlight.id != target_id)
    candidates = session.exec(query).all()
    if not candidates:
        return []

    candidate_ids = []
    candidate_vecs = []
    for c in candidates:
        candidate_ids.append(c.id)
        candidate_vecs.append(json.loads(c.embedding))

    candidate_matrix = np.array(candidate_vecs)

    # Gemini text-embedding-004 vectors are normalized, so dot product = cosine similarity
    similarities = np.dot(candidate_matrix, target_vec)
    
    # Get top K indices, descending
    top_indices = np.argsort(similarities)[::-1][:limit]

    return [candidates[i] for i in top_indices]
