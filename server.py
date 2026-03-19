"""CodeSnap — AI Code Explainer, Debugger, Converter, Optimizer
Fully async, with retry, rate limiting, error handling, and logging.
"""
import asyncio
import json
import logging
import os
import sys
import time
from collections import defaultdict
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ─── Config from env ───
API_KEY = os.getenv("KIMI_API_KEY", "")
MODEL = os.getenv("KIMI_MODEL", "kimi-for-coding")
API_URL = "https://api.kimi.com/coding/v1/chat/completions"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "User-Agent": "claude-code/1.0",
}

if not API_KEY:
    print("ERROR: KIMI_API_KEY not set. Create a .env file or set the environment variable.")
    print("See .env.example for reference.")
    sys.exit(1)

# ─── Logging ───
logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
logger = logging.getLogger("codesnap")

# ─── Rate limiting (in-memory, per IP) ───
_rate: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = 20  # per minute
RATE_WINDOW = 60

def _check_rate(ip: str) -> bool:
    now = time.time()
    _rate[ip] = [t for t in _rate[ip] if now - t < RATE_WINDOW]
    if len(_rate[ip]) >= RATE_LIMIT:
        return False
    _rate[ip].append(now)
    return True

# ─── Async HTTP client lifecycle ───
_client: httpx.AsyncClient | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _client
    _client = httpx.AsyncClient(timeout=60, headers=HEADERS)
    logger.info("CodeSnap started")
    yield
    await _client.aclose()
    logger.info("CodeSnap stopped")

app = FastAPI(title="CodeSnap", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ─── LLM call with retry ───
MAX_RETRIES = 2
RETRY_DELAY = 1

async def _call_llm(system: str, user: str) -> str:
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }
    last_err = ""
    t0 = time.time()
    for attempt in range(MAX_RETRIES + 1):
        try:
            r = await _client.post(API_URL, json=body)
            r.raise_for_status()
            result = r.json()["choices"][0]["message"]["content"]
            dur = int((time.time() - t0) * 1000)
            logger.info(f"LLM OK ({dur}ms, attempt {attempt+1})")
            return result
        except httpx.TimeoutException:
            last_err = "AI service timeout"
            logger.warning(f"LLM timeout (attempt {attempt+1})")
        except httpx.HTTPStatusError as e:
            last_err = f"AI service error: {e.response.status_code}"
            logger.warning(f"LLM HTTP {e.response.status_code} (attempt {attempt+1})")
        except Exception as e:
            last_err = str(e)
            logger.error(f"LLM error: {e} (attempt {attempt+1})")
        if attempt < MAX_RETRIES:
            await asyncio.sleep(RETRY_DELAY * (attempt + 1))
    raise HTTPException(502, {"error": last_err, "code": "LLM_FAILED"})

# ─── Models ───
from pydantic import Field

class CodeReq(BaseModel):
    code: str = Field(..., max_length=10000)
    lang: str = ""
    target_lang: str = ""

# ─── Rate limit middleware ───
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        ip = request.client.host if request.client else "unknown"
        if not _check_rate(ip):
            return JSONResponse({"error": "Rate limit exceeded (20/min)", "code": "RATE_LIMITED"}, status_code=429)
    return await call_next(request)

# ─── Routes ───
@app.get("/")
async def index():
    return FileResponse("static/index.html")

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.1.0"}

@app.post("/api/explain")
async def explain(req: CodeReq):
    return {"result": await _call_llm(
        "You are a code explainer. Explain clearly using bullet points. Match the language of code comments (Chinese→Chinese, else English). Be concise.",
        f"Explain this code:\n```{req.lang}\n{req.code}\n```"
    )}

@app.post("/api/debug")
async def debug(req: CodeReq):
    return {"result": await _call_llm(
        "You are a senior code reviewer. Find bugs, security issues, improvements. For each: state problem → show fix. Match comment language.",
        f"Review for bugs:\n```{req.lang}\n{req.code}\n```"
    )}

@app.post("/api/convert")
async def convert(req: CodeReq):
    if not req.target_lang:
        raise HTTPException(400, {"error": "target_lang required", "code": "MISSING_PARAM"})
    return {"result": await _call_llm(
        f"Convert to {req.target_lang}. Output ONLY the converted code in one code block. Translate comments.",
        f"Convert to {req.target_lang}:\n```{req.lang}\n{req.code}\n```"
    )}

@app.post("/api/optimize")
async def optimize(req: CodeReq):
    return {"result": await _call_llm(
        "You are a performance engineer. Optimize for speed and readability. Show optimized version with comments explaining changes. Match comment language.",
        f"Optimize:\n```{req.lang}\n{req.code}\n```"
    )}

@app.post("/api/document")
async def document(req: CodeReq):
    return {"result": await _call_llm(
        "Add comprehensive documentation to this code: docstrings, JSDoc, type annotations, inline comments for complex logic. Output the fully documented code.",
        f"Document this code:\n```{req.lang}\n{req.code}\n```"
    )}

@app.post("/api/test")
async def test(req: CodeReq):
    return {"result": await _call_llm(
        "Generate comprehensive unit tests for this code. Use the appropriate testing framework (pytest for Python, Jest for JS/TS, etc). Cover edge cases.",
        f"Generate tests for:\n```{req.lang}\n{req.code}\n```"
    )}

@app.post("/api/refactor")
async def refactor(req: CodeReq):
    return {"result": await _call_llm(
        "Refactor this code for better design patterns, readability, and maintainability. Explain each refactoring decision. Show before/after.",
        f"Refactor:\n```{req.lang}\n{req.code}\n```"
    )}

@app.post("/api/security")
async def security(req: CodeReq):
    return {"result": await _call_llm(
        "Perform a security audit. Check for: SQL injection, XSS, CSRF, path traversal, secrets exposure, insecure crypto, race conditions. Rate severity (Critical/High/Medium/Low).",
        f"Security scan:\n```{req.lang}\n{req.code}\n```"
    )}

# Static files (must be last)
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    print("⚡ CodeSnap at http://127.0.0.1:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080)
