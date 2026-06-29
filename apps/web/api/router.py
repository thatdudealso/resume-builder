from fastapi import APIRouter

from apps.web.api.v1 import auth, billing, exports, health, resumes, runs, score
from apps.web.api.v1.webhooks import crypto, stripe

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(resumes.router)
api_router.include_router(runs.router)
api_router.include_router(exports.router)
api_router.include_router(billing.router)
api_router.include_router(score.router)
api_router.include_router(stripe.router)
api_router.include_router(crypto.router)

health_router = APIRouter()
health_router.include_router(health.router)
