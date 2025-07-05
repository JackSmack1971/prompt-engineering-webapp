from prometheus_client import Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp
import time

# Define Prometheus metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

LLM_CALL_COUNT = Counter(
    'llm_calls_total',
    'Total LLM API calls',
    ['model_name', 'status']
)

LLM_TOKEN_COUNT = Counter(
    'llm_tokens_total',
    'Total LLM tokens used',
    ['model_name', 'direction']
)

# Middleware for automatic metrics collection
class MetricsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        method = request.method
        endpoint = request.url.path

        REQUEST_COUNT.labels(method=method, endpoint=endpoint).inc()

        start_time = time.time()
        response = await call_next(request)
        end_time = time.time()

        REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(end_time - start_time)

        return response

# Function to expose metrics
def get_metrics():
    return generate_latest()