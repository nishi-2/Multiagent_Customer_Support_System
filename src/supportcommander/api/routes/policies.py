from fastapi import APIRouter

from supportcommander.rag.policy_loader import load_all_policies


router = APIRouter(prefix="/api/v1/policies", tags=["Policies"])


@router.get("")
def list_policies() -> dict:
    policies = load_all_policies()

    return {
        "items": [
            {
                "policy_id": policy.policy_id,
                "title": policy.title,
                "version": policy.version,
                "category": policy.category,
            }
            for policy in policies
        ],

        "total": len(policies),
    }