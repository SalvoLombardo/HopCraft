#To aggregate all routes for API1


from fastapi import APIRouter

from app.api.v1.routes.search import router as search_router
from app.api.v1.routes.airports import router as airports_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(search_router, prefix="/search", tags=["search"])
api_router.include_router(airports_router, prefix="/airports", tags=["airports"])
