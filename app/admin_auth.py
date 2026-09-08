import os

from fastapi import Header, HTTPException


def require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    expected = os.getenv("ADMIN_API_TOKEN", "").strip()
    if not expected:
        return
    if x_admin_token != expected:
        raise HTTPException(status_code=401, detail="invalid admin token")
