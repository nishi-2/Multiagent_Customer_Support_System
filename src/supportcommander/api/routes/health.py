from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from supportcommander.core.constants import PROJECT_NAME, PROJECT_VERSION
from supportcommander.db.mongo import ping_database

router = APIRouter(tags=["Health"])

@router.get("/health")
def health_check() -> dict:
    return {
        "status": "ok",
        "service": PROJECT_NAME,
        "version": PROJECT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@router.get("/health/db")
def database_health_check() -> dict:
    try:
        ping_database()

        return {"status": "ok", "database": "mongodb",}

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is unavailable.",
        ) from exc