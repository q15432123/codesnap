"""Async LLM client — supports both full response and SSE streaming"""
import asyncio
import json
import logging
import time
from typing import AsyncGenerator

import httpx

from app.config import API_KEY, API_URL, MODEL

logger = logging.getLogger("codesnap.llm")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "User-Agent": "claude-code/1.0",
}

_client: httpx.AsyncClient | None = None

async def init_client():
    global _client
    _client = httpx.AsyncClient(timeout=60, headers=HEADERS)

async def close_client():
    global _client
    if _client:
        await _client.aclose()
        _client = None

MAX_RETRIES = 2

async def call(system: str, user: str) -> str:
    """Full response (non-streaming) with retry"""
    body = {"model": MODEL, "messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], "temperature": 0.3, "max_tokens": 4096}

    last_err = ""
    t0 = time.time()
    for attempt in range(MAX_RETRIES + 1):
        try:
            r = await _client.post(API_URL, json=body)
            r.raise_for_status()
            result = r.json()["choices"][0]["message"]["content"]
            logger.info(f"LLM OK ({int((time.time()-t0)*1000)}ms, attempt {attempt+1})")
            return result
        except httpx.TimeoutException:
            last_err = "AI service timeout"
        except httpx.HTTPStatusError as e:
            last_err = f"AI error {e.response.status_code}"
            if e.response.status_code == 429:
                last_err = "Rate limited by AI provider"
        except Exception as e:
            last_err = str(e)
        logger.warning(f"LLM attempt {attempt+1} failed: {last_err}")
        if attempt < MAX_RETRIES:
            await asyncio.sleep(1 * (attempt + 1))
    raise Exception(last_err)


async def call_stream(system: str, user: str) -> AsyncGenerator[str, None]:
    """SSE streaming — yields text chunks"""
    body = {"model": MODEL, "messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], "temperature": 0.3, "max_tokens": 4096, "stream": True}

    try:
        async with _client.stream("POST", API_URL, json=body) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    if delta.get("content"):
                        yield delta["content"]
                except (json.JSONDecodeError, IndexError, KeyError):
                    continue
    except Exception as e:
        yield f"\n[ERROR] {e}\n"
