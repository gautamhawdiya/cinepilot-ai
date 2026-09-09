import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

if sys.platform == "win32":
    # This machine's IPv6 route to Google's APIs is broken (confirmed:
    # direct IPv6 connections to aiplatform.googleapis.com/oauth2.googleapis
    # .com time out completely, every time, while IPv4 succeeds in ~2s),
    # while DNS still returns IPv6 addresses that Python's default resolver
    # can end up trying. Force IPv4-only resolution for every outbound
    # connection so nothing races the broken path.
    import socket

    _original_getaddrinfo = socket.getaddrinfo

    def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = _ipv4_only_getaddrinfo

    # Some Windows machines also have HTTPS traffic intercepted by
    # antivirus/VPN software whose root CA isn't in certifi's bundled list,
    # which makes outbound calls fail with "self-signed certificate in
    # certificate chain" even though the OS itself trusts the connection.
    # Falling back to the OS trust store fixes that without weakening
    # verification.
    import truststore

    truststore.inject_into_ssl()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.health import router as health_router
from api.routes.projects import router as projects_router


logger = logging.getLogger(__name__)


DEFAULT_DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

_configured_origins = os.getenv("CORS_ALLOWED_ORIGINS")
ALLOWED_ORIGINS = (
    [origin.strip() for origin in _configured_origins.split(",") if origin.strip()]
    if _configured_origins
    else DEFAULT_DEV_ORIGINS
)


async def _warm_up_vertex_credentials() -> None:
    """On some Windows dev machines, the *first* HTTPS connection to a Google
    auth host (oauth2.googleapis.com, for Vertex AI's ADC token refresh)
    reliably stalls for 30-120s before succeeding, while every connection
    after that is fast -- confirmed by repeated manual testing, and
    consistent with antivirus/DNS cold-path behavior rather than a real
    outage. Pay that one-time cost here at startup, well before a real
    pipeline run needs a token, instead of letting a user's first request
    eat it (or fail outright if it exceeds the request's own timeout).
    """
    if os.environ.get("GOOGLE_GENAI_USE_ENTERPRISE", "").lower() != "true":
        return

    import google.auth
    import google.auth.transport.requests

    for attempt in range(1, 4):
        try:
            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            await asyncio.to_thread(
                credentials.refresh, google.auth.transport.requests.Request()
            )
            logger.info("Vertex AI credentials warmed up successfully.")
            return
        except Exception as exc:
            logger.warning(
                "Vertex AI credential warm-up attempt %d/3 failed: %s",
                attempt,
                exc,
            )


@asynccontextmanager
async def _lifespan(_: FastAPI):
    # TestClient(app) used as a context manager runs this same lifespan --
    # never make a real network call from the test suite.
    if sys.platform == "win32" and "pytest" not in sys.modules:
        asyncio.create_task(_warm_up_vertex_credentials())
    yield


app = FastAPI(
    title="CinePilot AI API",
    version="0.1.0",
    description=(
        "API layer for the CinePilot AI production pipeline."
    ),
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(projects_router)
