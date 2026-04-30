import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.architecture import router as arch_router
from backend.routes.templates import router as tmpl_router

app = FastAPI(
    title="Cloud Architecture Solution Generator",
    description="Converts application descriptions into structured cloud architectures using LLM reasoning",
    version="1.0.0",
)

_extra_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"] + _extra_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(arch_router)
app.include_router(tmpl_router)


@app.get("/")
async def root():
    return {
        "name": "Cloud Architecture Solution Generator API",
        "version": "1.0.0",
        "docs": "/docs",
    }
