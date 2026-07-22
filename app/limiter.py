from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def get_real_client_ip(request: Request) -> str:
    # Behind the API Gateway / Render's edge proxy, request.client.host is the
    # proxy's IP — using it as the rate-limit key would bucket every user
    # together. Exactly one trusted hop appends the client's IP to
    # X-Forwarded-For; everything left of that hop is client-supplied and
    # spoofable (RFC 7239), so the rightmost entry is the only one this
    # service can trust, never the leftmost — taking the leftmost let any
    # caller bypass rate limiting entirely by sending a fresh fake value on
    # every request (confirmed via pentest: 15 consecutive failed logins with
    # a rotating X-Forwarded-For never tripped the 10/minute limit).
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[-1].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=get_real_client_ip)
