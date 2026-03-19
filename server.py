"""CodeSnap — 貼 code → AI 解釋 / 抓 bug / 翻譯"""
import json
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="CodeSnap")

# Kimi Code API
API_URL = "https://api.kimi.com/coding/v1/chat/completions"
API_KEY = "sk-kimi-KwvowsUEUXBCj5BBPtPr35n17aJMTEydmyGO6IeiFfw0HLqFYZKk5ZH5jdcduqJI"
MODEL = "kimi-for-coding"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "User-Agent": "claude-code/1.0",
}


def _call_llm(system: str, user: str) -> str:
    r = httpx.post(API_URL, headers=HEADERS, json={
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


class CodeReq(BaseModel):
    code: str
    lang: str = ""
    target_lang: str = ""


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.post("/api/explain")
async def explain(req: CodeReq):
    result = _call_llm(
        "You are a code explainer. Explain the code clearly in the SAME language as the code comments or variable names. "
        "If the code has Chinese comments, explain in Chinese. Otherwise explain in English. "
        "Use bullet points. Be concise.",
        f"Explain this code:\n```{req.lang}\n{req.code}\n```"
    )
    return {"result": result}


@app.post("/api/debug")
async def debug(req: CodeReq):
    result = _call_llm(
        "You are a senior code reviewer. Find bugs, security issues, and improvement opportunities. "
        "For each issue: state the problem, show the fix. Use the same language as the code comments. "
        "If no bugs found, say so and suggest improvements.",
        f"Review this code for bugs:\n```{req.lang}\n{req.code}\n```"
    )
    return {"result": result}


@app.post("/api/convert")
async def convert(req: CodeReq):
    if not req.target_lang:
        raise HTTPException(400, "target_lang required")
    result = _call_llm(
        f"Convert the code to {req.target_lang}. Output ONLY the converted code in a single code block. "
        "Keep the same logic and comments (translated).",
        f"Convert to {req.target_lang}:\n```{req.lang}\n{req.code}\n```"
    )
    return {"result": result}


@app.post("/api/optimize")
async def optimize(req: CodeReq):
    result = _call_llm(
        "You are a performance engineer. Optimize this code for speed and readability. "
        "Show the optimized version with comments explaining each change. "
        "Use the same language as the code comments.",
        f"Optimize this code:\n```{req.lang}\n{req.code}\n```"
    )
    return {"result": result}


app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    print("🔥 CodeSnap at http://127.0.0.1:8080")
    uvicorn.run(app, host="127.0.0.1", port=8080)
