import os
import sys

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


app = FastAPI(
    title="CinePilot AI API",
    version="0.1.0",
    description=(
        "API layer for the CinePilot AI production pipeline."
    ),
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
