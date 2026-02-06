from pydantic import BaseModel
from typing import Any, Optional


class ApiResponse(BaseModel):
    success: bool
    status_code: int
    payload: str


class ApiError(Exception):
    def __init__(self, status_code: int, payload: str, details: Optional[Any]):
        self.success = False
        self.status_code = status_code
        self.payload = payload
        self.details = details
