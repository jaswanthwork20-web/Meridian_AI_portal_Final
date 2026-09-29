"""
Unified Meridian Enterprise Helpdesk Backend Application
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import init_db
from knowledge_base.retriever import HybridRetriever
from app.config import CORS_ORIGINS, STATIC_DIR
from app.routers import auth, chat, remote, enterprise, agents, pages

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables and migrations
    init_db()
    # Initialize Hybrid Retriever
    HybridRetriever.get_instance()
    yield

app = FastAPI(
    title="Meridian Enterprise Helpdesk API",
    version="2.0.0",
    description="Enterprise IT & Finance Helpdesk with knowledge retrieval, remote remediation, and Jira integration",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# No-Cache headers middleware for static and HTML files
@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.endswith((".html", ".js", ".css")) or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Mount Modular Routers
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(remote.router)
app.include_router(enterprise.router)
app.include_router(agents.router)
app.include_router(pages.router)

# Mount Static Files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/health", tags=["Health"])
def health():
    retriever = HybridRetriever.get_instance()
    vectors = retriever.index.ntotal if retriever.index else 0
    return {"status": "ok", "vectors_indexed": vectors, "version": "2.0.0"}
