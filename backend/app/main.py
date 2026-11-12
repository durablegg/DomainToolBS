from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import auth, accounts, audit, batch, computers, domain, gpo, groups, ous, rbac, recyclebin, users
from app.core.config import get_settings
from app.db import init_db

settings = get_settings()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(accounts.router, prefix=settings.API_PREFIX)
app.include_router(domain.router, prefix=settings.API_PREFIX)
app.include_router(ous.router, prefix=settings.API_PREFIX)
app.include_router(users.router, prefix=settings.API_PREFIX)
app.include_router(groups.router, prefix=settings.API_PREFIX)
app.include_router(computers.router, prefix=settings.API_PREFIX)
app.include_router(audit.router, prefix=settings.API_PREFIX)
app.include_router(batch.router, prefix=settings.API_PREFIX)
app.include_router(gpo.router, prefix=settings.API_PREFIX)
app.include_router(rbac.router, prefix=settings.API_PREFIX)
app.include_router(recyclebin.router, prefix=settings.API_PREFIX)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    from app.services.scheduler import start_scheduler

    start_scheduler()


@app.on_event("shutdown")
def _shutdown() -> None:
    from app.services.scheduler import stop_scheduler

    stop_scheduler()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": settings.APP_NAME}


@app.exception_handler(Exception)
async def _unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """未捕获异常统一返回 JSON，避免前端只能看到「HTTP 500」这类无信息量的提示。"""
    logger.exception("未处理异常: %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": f"服务器内部错误：{exc}"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
