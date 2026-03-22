import logging
import pathlib
import secrets
import time

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from telegram_mailing_help.pwa.router_auth import router as auth_router
from telegram_mailing_help.pwa.router_user import router as user_router
from telegram_mailing_help.pwa.router_push import router as push_router

STATIC_PATH = str(pathlib.Path(__file__).parent.absolute()) + '/static/'

log = logging.getLogger("pwaServer")

# Module-level state — set by PwaServer.__init__, read by router helpers
_push_broadcaster = None

# Build the FastAPI app at module load
pwa_app = FastAPI(title="PWA API")

pwa_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwa_app.include_router(auth_router, prefix="/api/pwa/auth", tags=["auth"])
pwa_app.include_router(user_router, prefix="/api/pwa/user", tags=["user"])
pwa_app.include_router(push_router, prefix="/api/pwa/push", tags=["push"])

pwa_app.mount("/static", StaticFiles(directory=STATIC_PATH), name="pwa-static")


class _LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        await request.body()
        response = await call_next(request)
        elapsed = int((time.time() - start) * 100000) / 100.0
        log.info("PWA: %s %s [%s] %.1fms",
                 request.method, request.url.path, response.status_code, elapsed)
        return response


pwa_app.add_middleware(_LoggingMiddleware)


@pwa_app.get("/")
@pwa_app.get("/{path:path}")
def spa_fallback(path: str = ""):
    # Static files are served above; everything else → SPA shell
    return FileResponse(STATIC_PATH + "index.html")


class PwaServer:
    """Sets up PWA module globals (deps, push broadcaster, secrets).
    The actual HTTP serving is done by FastAPIServer.add_app() in the same event loop."""

    def __init__(self, appConfig, daoMap: dict, preparationMap: dict, botMap: dict):
        global _push_broadcaster
        self._appConfig = appConfig

        # Use the first (or only) bot's DAO/Prep
        first_key = list(daoMap.keys())[0]
        dao = daoMap[first_key]
        prep = preparationMap[first_key]

        # Wire module-level globals in deps module
        from telegram_mailing_help.pwa import deps
        deps._dao = dao
        deps._prep = prep
        deps._appConfig = appConfig

        # Build push broadcaster
        from telegram_mailing_help.pwa.push import PushBroadcaster
        _push_broadcaster = PushBroadcaster(dao, appConfig.pwa.vapid_subject)

        self._ensure_secrets(dao)

    def _ensure_secrets(self, dao):
        """Auto-generate JWT secret and VAPID keys on first startup."""
        jwt_secret = dao.getValueFromStorage("pwa_jwt_secret")
        if not jwt_secret:
            dao.setValueInfoStorage("pwa_jwt_secret", secrets.token_hex(32))
        from telegram_mailing_help.pwa.push import get_or_create_vapid_keys
        try:
            get_or_create_vapid_keys(dao)
        except Exception as e:
            log.warning("Could not generate VAPID keys: %s", e)

