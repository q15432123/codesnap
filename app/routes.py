"""API routes — DRY, one handler for all actions"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import CODE_MAX_LEN
from app.prompts import get_prompt, format_user
from app.llm import call, call_stream

router = APIRouter(prefix="/api")

class CodeReq(BaseModel):
    code: str = Field(..., max_length=CODE_MAX_LEN)
    lang: str = ""
    target_lang: str = ""
    stream: bool = False  # client can request SSE


ACTIONS = ["explain", "debug", "optimize", "document", "test", "refactor", "security"]

# Generate one route per action (DRY)
for _action in ACTIONS:
    def _make_handler(action: str):
        async def handler(req: CodeReq):
            sys_prompt = get_prompt(action)
            usr_prompt = format_user(action, req.code, req.lang)
            if req.stream:
                return StreamingResponse(
                    _sse_wrap(call_stream(sys_prompt, usr_prompt)),
                    media_type="text/event-stream",
                )
            try:
                result = await call(sys_prompt, usr_prompt)
                return {"result": result}
            except Exception as e:
                raise HTTPException(502, {"error": str(e), "code": "LLM_FAILED"})
        handler.__name__ = f"action_{action}"
        return handler
    router.post(f"/{_action}")(_make_handler(_action))


# Convert needs target_lang
@router.post("/convert")
async def convert(req: CodeReq):
    if not req.target_lang:
        raise HTTPException(400, {"error": "target_lang required", "code": "MISSING_PARAM"})
    sys_prompt = get_prompt("convert", target_lang=req.target_lang)
    usr_prompt = format_user("convert", req.code, req.lang, target_lang=req.target_lang)
    if req.stream:
        return StreamingResponse(
            _sse_wrap(call_stream(sys_prompt, usr_prompt)),
            media_type="text/event-stream",
        )
    try:
        result = await call(sys_prompt, usr_prompt)
        return {"result": result}
    except Exception as e:
        raise HTTPException(502, {"error": str(e), "code": "LLM_FAILED"})


async def _sse_wrap(gen):
    """Wrap async generator as SSE events"""
    try:
        async for chunk in gen:
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        yield f"data: [ERROR] {e}\n\n"
