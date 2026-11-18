"""Validated inputs for public report and retrieval endpoints."""
from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from backend.security.controls import validate_repository_url, validate_question

class AnalyzeRequest(BaseModel):
    url: str = Field(min_length=1,max_length=500)

    @field_validator('url')
    @classmethod
    def only_public_github(cls, value):
        return validate_repository_url(value)

class AskRequest(AnalyzeRequest):
    conversation_id: str | None = Field(default=None, max_length=36)
    version: int | None = Field(default=None, ge=0)
    question: str = Field(min_length=1,max_length=4000)

    @field_validator('question')
    @classmethod
    def safe_question(cls, value):
        return validate_question(value)

