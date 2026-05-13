"""
Cloudflare header guard middleware.
Enforces that requests arrive through Cloudflare by checking the
CF-Connecting-IP header.  Toggle with REQUIRE_CLOUDFLARE=true.
"""
from __future__ import annotations

import ipaddress
import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from config import settings

logger = logging.getLogger(__name__)


class CloudflareGuardMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, require: bool = True):
        super().__init__(app)
        self.require = require
        self._allowed_nets: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        if settings.CLOUDFLARE_ALLOWED_IPS:
            for cidr in settings.CLOUDFLARE_ALLOWED_IPS.split(","):
                cidr = cidr.strip()
                if cidr:
                    try:
                        self._allowed_nets.append(ipaddress.ip_network(cidr, strict=False))
                    except ValueError:
                        logger.warning("Invalid CIDR in CLOUDFLARE_ALLOWED_IPS: %s", cidr)

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.require:
            return await call_next(request)

        cf_ip = request.headers.get("CF-Connecting-IP")
        if not cf_ip:
            logger.warning("Blocked request missing CF-Connecting-IP header: %s", request.url)
            return JSONResponse(
                status_code=403,
                content={"detail": "Direct access not allowed"},
            )

        if self._allowed_nets:
            try:
                addr = ipaddress.ip_address(cf_ip)
                if not any(addr in net for net in self._allowed_nets):
                    logger.warning("CF-Connecting-IP %s not in allowed networks", cf_ip)
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Access denied"},
                    )
            except ValueError:
                logger.warning("Invalid CF-Connecting-IP value: %s", cf_ip)
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Access denied"},
                )

        return await call_next(request)
