"""FastAPI app — middleware, lifecycle, static files"""
import logging
import os
import sys
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import API_KEY, CORS_ORIGINS, RATE_LIMIT, VERSION
from app.llm import init_client, close_client
from app.routes import router

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
logger = logging.getLogger("codesnap")

if not API_KEY:
    print("ERROR: KIMI_API_KEY not set. Create .env or set env var. See .env.example")
    sys.exit(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_client()
    logger.info(f"CodeSnap v{VERSION} started")
    yield
    await close_client()

app = FastAPI(title="CodeSnap", version=VERSION, lifespan=lifespan)

# CORS
origins = CORS_ORIGINS.split(",") if CORS_ORIGINS != "*" else ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

# Rate limit (in-memory)
_rate: dict[str, list[float]] = defaultdict(list)

@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        _rate[ip] = [t for t in _rate[ip] if now - t < 60]
        if len(_rate[ip]) >= RATE_LIMIT:
            retry_after = int(60 - (now - _rate[ip][0]))
            return JSONResponse(
                {"error": f"Rate limit exceeded ({RATE_LIMIT}/min)", "code": "RATE_LIMITED",
                 "retry_after": max(1, retry_after)},
                status_code=429,
                headers={"Retry-After": str(max(1, retry_after))},
            )
        _rate[ip].append(now)
    return await call_next(request)

# Routes
app.include_router(router)

@app.get("/")
async def index():
    return FileResponse("static/index.html")

@app.get("/health")
async def health():
    return {"status": "ok", "version": VERSION}

# Static (last)
app.mount("/static", StaticFiles(directory="static"), name="static")
