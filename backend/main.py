import sys
import asyncio
import logging
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import API_HOST, API_PORT
from backend.database import init_db, close_db, async_session_factory
from backend.routers import products, customers, audit_logs, imports, delivery_notes, statements, ai

logger = logging.getLogger(__name__)


async def scheduled_cleanup():
    """每 6 小时清理一次超过 7 天未活跃的 AI 会话。"""
    while True:
        await asyncio.sleep(3600 * 6)
        try:
            async with async_session_factory() as db:
                from backend.services.ai_service import cleanup_stale_sessions
                await cleanup_stale_sessions(db)
        except Exception as e:
            logger.warning("Session cleanup failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期管理器：应用启动时初始化数据库和加载 AI 会话，关闭时清理连接池。"""
    await init_db()
    # 从 DB 加载 AI 会话到内存缓存
    from backend.services.ai_service import load_sessions_from_db
    async with async_session_factory() as db:
        await load_sessions_from_db(db)
    # 启动定时清理任务
    cleanup_task = asyncio.create_task(scheduled_cleanup())
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    await close_db()


app = FastAPI(title="InventorySales", version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)
app.include_router(customers.router)
app.include_router(audit_logs.router)
app.include_router(imports.router)
app.include_router(delivery_notes.router)
app.include_router(statements.router)
app.include_router(ai.router)


@app.get("/api/health")
async def health():
    """健康检查接口。"""
    return {"status": "ok", "version": "0.3.0"}


frontend_dist = project_root / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host=API_HOST, port=API_PORT, reload=False)
