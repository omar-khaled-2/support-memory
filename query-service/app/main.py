from fastapi import FastAPI

from app.views import router as query_router


app = FastAPI(title="Query Service")
app.include_router(query_router, prefix="/api/v1")
