import json
import logging
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import Request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware

# ---------- Logger (structured JSON) ----------
logger = logging.getLogger("checkout-service")

def _json_log(level: str, payload: Dict[str, Any]) -> None:
    # Keep logs one-line JSON for easy parsing
    msg = json.dumps(payload, ensure_ascii=False)
    getattr(logger, level.lower(), logger.info)(msg)

def _extract_session_id_from_body(body_bytes: bytes) -> Optional[str]:
    # Only best-effort (never fail the request)
    try:
        if not body_bytes:
            return None
        data = json.loads(body_bytes.decode("utf-8"))
        # Our APIs use session_id in body
        return data.get("session_id")
    except Exception:
        return None


# ---------- Prometheus metrics ----------
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["service", "method", "path", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["service", "method", "path"],
)

CHECKOUT_SERVICE_NAME = "checkout-service"


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())

        # Read body safely (Starlette caches it; we set it back explicitly)
        body = b""
        try:
            body = await request.body()
            request._body = body  # allow downstream to read body normally
        except Exception:
            body = b""

        session_id = _extract_session_id_from_body(body)

        start = time.perf_counter()
        status_code = 500

        try:
            response: Response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            # Log exception and re-raise
            _json_log(
                "error",
                {
                    "service": CHECKOUT_SERVICE_NAME,
                    "event": "request_error",
                    "request_id": request_id,
                    "method": request.method,
                    "path": str(request.url.path),
                    "session_id": session_id,
                    "error": repr(e),
                },
            )
            raise
        finally:
            dur_s = time.perf_counter() - start
            dur_ms = round(dur_s * 1000, 2)

            # metrics
            REQUEST_COUNT.labels(
                CHECKOUT_SERVICE_NAME, request.method, request.url.path, str(status_code)
            ).inc()
            REQUEST_LATENCY.labels(
                CHECKOUT_SERVICE_NAME, request.method, request.url.path
            ).observe(dur_s)

            # logs
            _json_log(
                "info",
                {
                    "service": CHECKOUT_SERVICE_NAME,
                    "event": "request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": str(request.url.path),
                    "status_code": status_code,
                    "latency_ms": dur_ms,
                    "session_id": session_id,
                },
            )

        # Return request id back to client
        response.headers["x-request-id"] = request_id
        return response


def setup_observability(app) -> None:
    # logging config once
    logging.basicConfig(level=logging.INFO)

    # middleware
    app.add_middleware(ObservabilityMiddleware)

    # /metrics endpoint
    @app.get("/metrics")
    def metrics():
        data = generate_latest()
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)