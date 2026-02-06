from typing import List
from pydantic import BaseModel


class GuardrailResult(BaseModel):
    is_valid: bool
    issues: List[str]
