from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.duplicates import router as duplicates_router
from app.api.routes.health import router as health_router
from app.api.routes.ingestion import router as ingestion_router
from app.api.routes.institutions import router as institutions_router
from app.api.routes.privacy import router as privacy_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(institutions_router)
api_router.include_router(auth_router)
api_router.include_router(ingestion_router)
api_router.include_router(duplicates_router)
api_router.include_router(privacy_router)
