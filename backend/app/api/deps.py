"""
FastAPI Dependencies
====================
Shared dependency injection for authentication and database session management.
"""
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, ExpiredSignatureError
from sqlalchemy import text

from app.core.auth import decode_token, current_family_id, current_user_id
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

# OAuth2 Bearer scheme for Swagger UI
security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> dict:
    """
    Validates the Bearer JWT and returns the decoded claims.
    Sets the ContextVar for RLS family scoping.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_token(token)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Set context vars for RLS
    family_id = payload.get("family_id")
    user_id = payload.get("sub")
    if family_id:
        current_family_id.set(family_id)
    if user_id:
        current_user_id.set(user_id)

    return payload


async def get_db():
    """
    Yields an async database session with the RLS context set.
    The family_id is read from the ContextVar set by get_current_user.
    """
    async with AsyncSessionLocal() as session:
        fid = current_family_id.get(None)
        if fid:
            # SET LOCAL scopes the variable to the current transaction only
            await session.execute(
                text("SET LOCAL app.current_family_id = :fid"),
                {"fid": str(fid)},
            )
        yield session


def require_parent(user: dict = Depends(get_current_user)) -> dict:
    """Dependency that ensures the caller has the 'parent' role."""
    if user.get("role") != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Parent role required",
        )
    return user


def require_scope(required_scope: str):
    """Factory that returns a dependency checking for a specific scope."""
    def _check(user: dict = Depends(get_current_user)) -> dict:
        if user.get("scope") != required_scope:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Scope '{required_scope}' required",
            )
        return user
    return _check
