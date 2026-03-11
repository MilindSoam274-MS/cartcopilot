import json
import logging
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import Request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware

# =========================
# Logger (structured one-line JSON)
# =========================
logger = logging.getLogger("assistant-service")


def _json_log(level: str, payload: Dict[str, Any]) -> None:
    msg = json.dumps(payload, ensure_ascii=False)
    getattr(logger, level.lower(), logger.info)(msg)


def _extract_session_id_from_body(body_bytes: bytes) -> Optional[str]:
    try:
        if not body_bytes:
            return None
        data = json.loads(body_bytes.decode("utf-8"))
        return data.get("session_id")
    except Exception:
        return None


# =========================
# Infra / HTTP Metrics
# =========================
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["service", "method", "path", "status_code"],
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["service", "method", "path"],
)

ASSISTANT_SERVICE_NAME = "assistant-service"


# =========================
# Assistant Business Metrics
# =========================
ASSISTANT_MESSAGES_TOTAL = Counter(
    "assistant_messages_total",
    "Total assistant messages by resolved intent",
    ["intent"],
)

ASSISTANT_LOW_CONFIDENCE_TOTAL = Counter(
    "assistant_low_confidence_total",
    "Total assistant responses with low confidence",
)

ASSISTANT_FALLBACK_TOTAL = Counter(
    "assistant_fallback_total",
    "Total assistant fallback / clarification responses",
)

ASSISTANT_CART_ADD_TOTAL = Counter(
    "assistant_cart_add_total",
    "Total successful add-to-cart actions",
)

ASSISTANT_CART_REMOVE_TOTAL = Counter(
    "assistant_cart_remove_total",
    "Total successful remove-from-cart actions",
)

ASSISTANT_SHOW_CART_TOTAL = Counter(
    "assistant_show_cart_total",
    "Total show-cart actions",
)

ASSISTANT_CLEAR_CART_TOTAL = Counter(
    "assistant_clear_cart_total",
    "Total clear-cart actions",
)

ASSISTANT_UPDATE_CART_QTY_TOTAL = Counter(
    "assistant_update_cart_qty_total",
    "Total cart quantity update actions",
)

# =========================
# Retrieval Metrics
# =========================
ASSISTANT_RETRIEVAL_CALLS_TOTAL = Counter(
    "assistant_retrieval_calls_total",
    "Total retrieval-service calls made by assistant-service",
    ["status"],  # success | error
)

ASSISTANT_RETRIEVAL_LATENCY = Histogram(
    "assistant_retrieval_latency_seconds",
    "Latency of retrieval-service calls from assistant-service",
)

# =========================
# LLM Metrics
# =========================
ASSISTANT_LLM_CALLS_TOTAL = Counter(
    "assistant_llm_calls_total",
    "Total LLM response-generation calls made by assistant-service",
    ["status"],  # success | error
)

ASSISTANT_LLM_LATENCY = Histogram(
    "assistant_llm_latency_seconds",
    "Latency of LLM response-generation calls in assistant-service",
)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())

        body = b""
        try:
            body = await request.body()
            request._body = body
        except Exception:
            body = b""

        session_id = _extract_session_id_from_body(body)

        start = time.perf_counter()
        status_code = 500

        try:
            response: Response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            _json_log(
                "error",
                {
                    "service": ASSISTANT_SERVICE_NAME,
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

            HTTP_REQUESTS_TOTAL.labels(
                ASSISTANT_SERVICE_NAME, request.method, request.url.path, str(status_code)
            ).inc()

            HTTP_REQUEST_DURATION.labels(
                ASSISTANT_SERVICE_NAME, request.method, request.url.path
            ).observe(dur_s)

            _json_log(
                "info",
                {
                    "service": ASSISTANT_SERVICE_NAME,
                    "event": "request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": str(request.url.path),
                    "status_code": status_code,
                    "latency_ms": dur_ms,
                    "session_id": session_id,
                },
            )

        response.headers["x-request-id"] = request_id
        return response


def setup_observability(app) -> None:
    logging.basicConfig(level=logging.INFO)
    app.add_middleware(ObservabilityMiddleware)

    @app.get("/metrics")
    def metrics():
        data = generate_latest()
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)