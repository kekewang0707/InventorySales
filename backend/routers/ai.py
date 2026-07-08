"""AI 快捷操作路由

- POST /api/ai/command — 接收用户文本，返回 AI 回复
- POST /api/ai/confirm — 用户确认写入操作后执行
- GET  /api/ai/command/stream — SSE 流式响应（v2 新增）
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage

from backend.database import get_db
from backend.services.ai_service_v2 import (
    handle_command,
    execute_pending,
    get_all_sessions_info,
    get_session_messages,
    rename_session,
    delete_session,
)
from backend.services.agent_state import (
    get_checkpointer,
    build_config,
    ensure_session_exists,
)
from backend.services.agent_factory import build_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])


# ---- Request / Response Models ----

class CommandRequest(BaseModel):
    text: str
    session_id: str = ""


class ConfirmRequest(BaseModel):
    confirm_id: str


class RenameRequest(BaseModel):
    title: str


class CommandResponse(BaseModel):
    action: str  # "queried" | "needs_confirm" | "error" | "executed"
    reply: str
    confirm_id: Optional[str] = None
    tool_calls: Optional[list] = None
    session_id: str = ""


class SessionInfoResponse(BaseModel):
    session_id: str
    message_count: int
    first_message: str = ""
    title: str = ""
    last_active: str = ""
    created_at: str = ""


# ---- 同步端点（保持向后兼容） ----

@router.post("/command", response_model=CommandResponse)
async def ai_command(
    req: CommandRequest,
    db: AsyncSession = Depends(get_db),
):
    """接收用户文本指令，由 AI 服务处理后返回回复（查询/确认/执行）。"""
    result = await handle_command(req.text, db, session_id=req.session_id)
    return CommandResponse(**result)


@router.post("/confirm", response_model=CommandResponse)
async def ai_confirm(
    req: ConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    """用户确认写入操作后执行对应的 AI 工具函数。"""
    result = await execute_pending(req.confirm_id, db)
    return CommandResponse(**result)


# ---- Session CRUD 端点 ----

@router.get("/sessions", response_model=list[SessionInfoResponse])
async def list_sessions():
    """列出当前所有活跃会话的元信息（用于前端 tab 切换）。"""
    return get_all_sessions_info()


@router.get("/sessions/{session_id}/messages")
async def get_session_messages_endpoint(session_id: str, db: AsyncSession = Depends(get_db)):
    """获取指定会话的消息列表。"""
    msgs = await get_session_messages(session_id, db)
    return {"session_id": session_id, "messages": msgs}


@router.delete("/sessions/{session_id}")
async def delete_session_route(session_id: str, db: AsyncSession = Depends(get_db)):
    """删除指定会话及其消息（内存 + DB + LangGraph checkpoint）。"""
    ok = await delete_session(session_id, db)
    return {"deleted": ok}


@router.patch("/sessions/{session_id}/title")
async def rename_session_endpoint(session_id: str, req: RenameRequest, db: AsyncSession = Depends(get_db)):
    """修改会话标题。"""
    ok = await rename_session(session_id, req.title, db)
    return {"renamed": ok}


# ---- SSE 流式端点（v2 新增） ----

@router.get("/command/stream")
async def ai_command_stream(
    text: str = Query(..., description="用户输入文本"),
    session_id: str = Query("", description="会话ID，不传则自动创建"),
    db: AsyncSession = Depends(get_db),
):
    """SSE 流式端点：实时推送 Agent 的推理和执行过程。

    事件类型:
      - "thinking"     Agent 正在推理
      - "tool_call"    正在调用查询工具
      - "tool_result"  查询工具返回结果
      - "needs_confirm" 需要用户确认写入操作
      - "answer"       AI 最终回复的文本块
      - "done"         执行完成
      - "error"        执行出错
    """

    async def event_generator():
        from backend.config import is_openai_configured

        if not text.strip():
            yield _sse_event("error", "请输入指令")
            return

        if not is_openai_configured():
            # 离线模式不支持流式，直接返回结果
            from backend.services.ai_service_v2 import _try_offline
            result = await _try_offline(text, db)
            yield _sse_event("answer", result.get("reply", ""))
            yield _sse_event("done", {"session_id": result.get("session_id", "")})
            return

        try:
            sid, _ = await ensure_session_exists(db, session_id)
            checkpointer = await get_checkpointer()
            agent, _ = await build_agent(checkpointer)
            config = build_config(sid, db)

            yield _sse_event("thinking", {"session_id": sid})

            async for event in agent.astream_events(
                {"messages": [HumanMessage(content=text)]},
                config=config,
                version="v2",
            ):
                kind = event.get("event", "")

                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and chunk.content:
                        yield _sse_event("answer", chunk.content)

                elif kind == "on_tool_start":
                    tool_name = event.get("name", "")
                    tool_input = event.get("data", {}).get("input", {})
                    yield _sse_event("tool_call", {"name": tool_name, "input": tool_input})

                elif kind == "on_tool_end":
                    tool_output = event.get("data", {}).get("output", "")
                    yield _sse_event("tool_result", {"output": str(tool_output)})

            yield _sse_event("done", {"session_id": sid})

        except Exception as e:
            logger.error("SSE stream error: %s", e)
            yield _sse_event("error", str(e))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse_event(event: str, data) -> str:
    """构建 SSE 格式的事件字符串。"""
    if isinstance(data, str):
        payload = json.dumps({"data": data}, ensure_ascii=False)
    else:
        payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"
