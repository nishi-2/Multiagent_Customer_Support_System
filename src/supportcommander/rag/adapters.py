from supportcommander.graph.models import RetrievedPolicy
from supportcommander.rag.models import PolicySearchResult


def to_retrieved_policy(result: PolicySearchResult) -> RetrievedPolicy:

    return RetrievedPolicy(
        policy_id=result.policy_id,
        title=f"{result.policy_title} - {result.section}",
        content=result.content,
        source="policy_rag",
        relevance_score=result.similarity_score,
    )