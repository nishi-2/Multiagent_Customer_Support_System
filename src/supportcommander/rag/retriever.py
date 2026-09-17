from __future__ import annotations

import logging

from supportcommander.db.mongo import get_database
from supportcommander.rag.models import PolicySearchResult
from supportcommander.rag.similarity import cosine_similarity
from supportcommander.services.embedding_service import generate_embedding
from supportcommander.rag.adapters import to_retrieved_policy

logger = logging.getLogger(__name__)

KB_SIMILARITY_THRESHOLD = 0.55


INTENT_POLICY_CATEGORIES = {
    "refund_request": [
        "Refund",
        "Risk",
        "Escalation",
    ],

    "cancellation_request": [
        "Cancellation",
        "Risk",
        "Escalation",
    ],

    "technical_issue": [
        "Replacement",
        "Risk",
        "Escalation",
    ],

    "billing_inquiry": [
        "Billing",
        "Risk",
        "Escalation",
    ],

    "product_inquiry": [
        "Replacement",
    ],
}


async def retrieve_policies(query: str, *, top_k: int = 3, categories: list[str] | None = None) -> list[PolicySearchResult]:

    if top_k < 1:
        raise ValueError("top_k must be at least 1")

    query_embedding_result = await generate_embedding(query)
    db = get_database()
    mongo_query = {}

    if categories:
        mongo_query["category"] = {"$in": categories}

    documents = list(db.policy_chunks.find(mongo_query, {"_id": 0}))

    if not documents:
        raise RuntimeError("No policy chunks found for the requested search criteria. Run build_policy_index.py first.")

    scored = []

    for document in documents:
        score = cosine_similarity(query_embedding_result.embedding, document["embedding"],)

        scored.append(
            PolicySearchResult(
                chunk_id=document["chunk_id"],
                policy_id=document["policy_id"],
                policy_title=document["policy_title"],
                category=document["category"],
                section=document["section"],
                content=document["content"],
                similarity_score=score,
            )
        )

    scored.sort(
        key=lambda item: (item.similarity_score),
        reverse=True,
    )

    return scored[:top_k]


async def retrieve_for_intent(query: str, *, intent: str, top_k: int = 3) -> list[PolicySearchResult]:

    categories = INTENT_POLICY_CATEGORIES.get(intent)

    return await retrieve_policies(
        query,
        top_k=top_k,
        categories=categories,
    )


async def retrieve_for_graph(query: str, *, intent: str, top_k: int = 3):

    results = await retrieve_for_intent(query, intent=intent, top_k=top_k)

    return [to_retrieved_policy(result) for result in results]


async def retrieve_kb_docs(
    query: str,
    *,
    top_k: int = 5,
    threshold: float = KB_SIMILARITY_THRESHOLD,
) -> list:
    """
    Embed *query* and find the most relevant uploaded KB chunks.
    Returns a list of RetrievedPolicy objects with source_type='company_doc'.
    Returns [] (not raises) when no documents are uploaded yet.
    """
    from supportcommander.graph.models import RetrievedPolicy

    db = get_database()
    chunks = list(db.kb_chunks.find({}, {"_id": 0}))

    if not chunks:
        return []

    try:
        query_emb = await generate_embedding(query)
    except Exception as exc:
        logger.warning("KB retrieval: embedding failed — %s", exc)
        return []

    scored: list[tuple[float, dict]] = []
    for chunk in chunks:
        emb = chunk.get("embedding")
        if not emb:
            continue
        score = cosine_similarity(query_emb.embedding, emb)
        if score >= threshold:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)

    results: list[RetrievedPolicy] = []
    cited_doc_ids: set[str] = set()

    for score, chunk in scored[:top_k]:
        filename = chunk.get("filename", "uploaded document")
        doc_id   = chunk.get("doc_id", "")
        cited_doc_ids.add(doc_id)
        results.append(
            RetrievedPolicy(
                policy_id     = f"kb:{doc_id}:{chunk.get('chunk_index', 0)}",
                title         = filename,
                content       = chunk["content"],
                source        = "kb_rag",
                source_type   = "company_doc",
                citation      = filename,
                relevance_score = round(score, 4),
            )
        )

    if cited_doc_ids:
        db.kb_documents.update_many(
            {"doc_id": {"$in": list(cited_doc_ids)}},
            {"$inc": {"times_cited": 1}},
        )

    logger.info(
        "KB retrieval | query_len=%d matched=%d/%d docs_cited=%d",
        len(query), len(results), len(chunks), len(cited_doc_ids),
    )

    return results