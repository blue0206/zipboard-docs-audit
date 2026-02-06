from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from ..models.api import ApiError
from .config import env_settings

security = HTTPBearer()


async def authenticate_request(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> None:
    """
    Dependency to get the id of the current user from the provided token.
    """

    token = credentials.credentials

    if token != env_settings.AUTH_TOKEN:
        raise ApiError(
            status_code=401, payload="Invalid authentication token", details=None
        )
