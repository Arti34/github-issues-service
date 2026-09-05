from typing import Optional
from pydantic import BaseModel, Field

class IssueCreate(BaseModel):
    title: str = Field(..., min_length=1)
    body: Optional[str] = None
    labels: list[str] = []

class IssueUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1)
    body: Optional[str] = None
    state: Optional[str] = None

class CommentCreate(BaseModel):
    body: str = Field(..., min_length=1)

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
