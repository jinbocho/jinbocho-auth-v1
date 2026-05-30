# auth-service

`auth-service` manages families, users, roles, and local JWT-based authentication for Jinbocho.

## Responsibilities

- Register a family and its initial admin user.
- Authenticate users with email and password.
- Issue access and refresh tokens.
- Manage families and users.

## Environment variables

| Variable | Description |
|---|---|
| `DEBUG` | Enables debug SQL logging |
| `DATABASE_URL` | Async SQLAlchemy connection string |
| `JWT_SECRET_KEY` | Secret used to sign JWTs |
| `JWT_ALGORITHM` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime |

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

## Run with Docker

```bash
docker build -t jinbocho-auth-service .
docker run --rm -p 8001:8001 --env-file .env jinbocho-auth-service
```

## Health check

- `GET /health`

## Notes

- The service creates its tables on startup for scaffolding convenience.
- `login` is functional; `refresh` and `logout` are intentionally placeholder endpoints for the next iteration.
