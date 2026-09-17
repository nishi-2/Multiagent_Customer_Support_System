from pydantic import BaseModel

class PolicyChunk(BaseModel):
    chunk_id: str
    policy_id: str
    policy_title: str
    policy_version: str
    category: str
    section: str
    content: str
    source_path: str


class PolicySearchResult(BaseModel):
    chunk_id: str
    policy_id: str
    policy_title: str
    category: str
    section: str
    content: str

    similarity_score: float