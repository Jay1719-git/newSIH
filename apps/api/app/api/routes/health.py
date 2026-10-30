from fastapi import APIRouter

from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, operation_id="getHealth")
def get_health() -> HealthResponse:
    return HealthResponse()
