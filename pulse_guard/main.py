"""
应用入口模块。
"""
import logging
from typing import Dict, Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pulse_guard.api.routes import router as api_router

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,  # 开发时使用 DEBUG 级别，生产环境可以改为 INFO
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# 设置特定模块的日志级别
logging.getLogger("pulse_guard.api.webhook").setLevel(logging.DEBUG)
logging.getLogger("pulse_guard.tools.github").setLevel(logging.DEBUG)

# 降低一些库的日志级别，避免日志过多
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="Pulse Guard",
    description="自动化 PR 代码质量审查工具",
    version="0.1.0"
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router, prefix="/api")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """全局异常处理器"""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "服务内部错误"}
    )


@app.get("/")
async def root() -> Dict[str, Any]:
    """根路径处理器"""
    return {
        "name": "Pulse Guard",
        "description": "自动化 PR 代码质量审查工具",
        "version": "0.1.0"
    }


if __name__ == "__main__":
    uvicorn.run("pulse_guard.main:app", host="0.0.0.0", port=8000, reload=True)
