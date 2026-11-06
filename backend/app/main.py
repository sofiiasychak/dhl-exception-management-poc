import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from app.features.auth.router import router as auth_router
from app.features.cases.router import router as cases_router
from app.features.communication.router import router as communication_router
from app.features.field.router import router as field_router
from app.features.webhooks.router import router as webhooks_router


local_dev = os.getenv("LOCAL_DEV", "").lower() == "true"
app = FastAPI(
    title="Exception Management API",
    docs_url="/docs" if local_dev else None,
    redoc_url=None,
    openapi_url="/openapi.json" if local_dev else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Webhook-Secret"],
)
for router in (
    auth_router,
    cases_router,
    communication_router,
    field_router,
    webhooks_router,
):
    app.include_router(router)

handler = Mangum(app)
