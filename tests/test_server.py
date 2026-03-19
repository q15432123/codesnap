"""CodeSnap API tests — mock LLM responses"""
import os
os.environ["KIMI_API_KEY"] = "test-key-for-ci"

import pytest
import pytest_asyncio
import respx
import httpx
from httpx import AsyncClient, ASGITransport

import server as srv
from server import app

MOCK_LLM_RESPONSE = {
    "choices": [{"message": {"content": "This function adds two numbers."}}]
}
LLM_URL = "https://api.kimi.com/coding/v1/chat/completions"


@pytest_asyncio.fixture(autouse=True)
async def setup_client():
    srv._client = httpx.AsyncClient(timeout=10, headers=srv.HEADERS)
    yield
    await srv._client.aclose()
    srv._client = None


@pytest.fixture
def mock_llm():
    with respx.mock(assert_all_called=False) as r:
        r.post(LLM_URL).mock(return_value=httpx.Response(200, json=MOCK_LLM_RESPONSE))
        yield r


def _ac():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_health():
    async with _ac() as c:
        r = await c.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_explain(mock_llm):
    async with _ac() as c:
        r = await c.post("/api/explain", json={"code": "def add(a,b): return a+b", "lang": "python"})
        assert r.status_code == 200
        assert "result" in r.json()


@pytest.mark.asyncio
async def test_debug(mock_llm):
    async with _ac() as c:
        r = await c.post("/api/debug", json={"code": "x = 1/0"})
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_convert_missing_target():
    async with _ac() as c:
        r = await c.post("/api/convert", json={"code": "print('hi')"})
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_convert(mock_llm):
    async with _ac() as c:
        r = await c.post("/api/convert", json={"code": "print('hi')", "target_lang": "javascript"})
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_optimize(mock_llm):
    async with _ac() as c:
        r = await c.post("/api/optimize", json={"code": "for i in range(100): pass"})
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_code_too_long():
    async with _ac() as c:
        r = await c.post("/api/explain", json={"code": "x" * 10001})
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_document(mock_llm):
    async with _ac() as c:
        r = await c.post("/api/document", json={"code": "def foo(): pass"})
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_security(mock_llm):
    async with _ac() as c:
        r = await c.post("/api/security", json={"code": "eval(input())"})
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_llm_failure():
    with respx.mock() as m:
        m.post(LLM_URL).mock(return_value=httpx.Response(500, json={"error": "down"}))
        async with _ac() as c:
            r = await c.post("/api/explain", json={"code": "x=1"})
            assert r.status_code == 502
