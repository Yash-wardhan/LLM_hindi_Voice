from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

security = HTTPBearer(auto_error=False)


async def get_current_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> str:
    """
    Dependency to extract and validate Bearer token.
    Replace the stub validation with your real auth logic.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
        )
    token = credentials.credentials
    # TODO: validate token (e.g. JWT decode)
    return token


# Reusable annotated dependency alias
CurrentToken = Annotated[str, Depends(get_current_token)]
