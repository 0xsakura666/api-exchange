import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional

from config import get_settings
from database import db
from models import ChatCompletionRequest
from proxy import api_proxy
import admin

settings = get_settings()
security = HTTPBearer(auto_error=False)


async def verify_api_key(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """验证 API Key（支持使用 admin_key 作为统一的访问密钥）"""
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Use Authorization: Bearer <your-key>"
        )
    
    if credentials.credentials != settings.admin_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    return credentials.credentials


async def periodic_sync():
    """后台定期同步用量"""
    while True:
        try:
            await asyncio.sleep(settings.sync_interval)
            if settings.auto_sync_usage:
                await usage_checker.sync_all_keys(batch_size=5)
        except asyncio.CancelledError:
            break
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    await db.connect()
    
    sync_task = None
    if settings.auto_sync_usage:
        sync_task = asyncio.create_task(periodic_sync())
    
    yield
    
    if sync_task:
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass
    
    await db.disconnect()


app = FastAPI(
    title="API Exchange",
    description="API Key 中转服务 - 自动管理多个 API Key，用完自动切换",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin.router)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

if os.path.exists(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")


@app.get("/")
async def root():
    """首页 - 如果有前端则返回前端页面"""
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    
    stats = await db.get_stats()
    return {
        "service": "API Exchange",
        "version": "1.0.0",
        "status": "running",
        "keys": {
            "total": stats.total_keys,
            "active": stats.active_keys,
            "total_balance": stats.total_balance
        }
    }


@app.get("/api/status")
async def api_status():
    """API 状态"""
    stats = await db.get_stats()
    return {
        "service": "API Exchange",
        "version": "1.0.0",
        "status": "running",
        "keys": {
            "total": stats.total_keys,
            "active": stats.active_keys,
            "total_balance": stats.total_balance
        }
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "healthy"}


@app.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    _: str = Depends(verify_api_key)
):
    """
    OpenAI 兼容的 Chat Completions 接口
    
    模型名称会直接透传给上游 API
    """
    return await api_proxy.chat_completions(request)


@app.get("/v1/models")
async def list_models(_: str = Depends(verify_api_key)):
    """获取可用模型列表"""
    return await api_proxy.list_models()


@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_other(
    path: str,
    request: Request,
    _: str = Depends(verify_api_key)
):
    """代理其他 OpenAI API 端点（如果需要）"""
    raise HTTPException(
        status_code=501,
        detail=f"Endpoint /v1/{path} is not implemented. Only /v1/chat/completions and /v1/models are supported."
    )


@app.get("/{path:path}")
async def catch_all(path: str):
    """捕获所有其他路径，返回前端页面（SPA 支持）"""
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    raise HTTPException(status_code=404, detail="Not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
