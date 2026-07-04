from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def get_real_client_ip(request: Request) -> str:
    # Behind the API Gateway / Render's edge proxy, request.client.host is the
    # proxy's IP — using it as the rate-limit key would bucket every user
    # together. The proxy appends the original client IP as the first entry
    # of X-Forwarded-For.
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=get_real_client_ip)
