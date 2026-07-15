"""Versioned schemas for the public gold-QA benchmark and its results."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class GoldQuestion(BaseModel):
    question_id: str
    question: str
    expected_document_ids: list[str] = Field(min_length=1)


class GoldDataset(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    benchmark_version: str
    questions: list[GoldQuestion] = Field(min_length=1)


class EvaluationMetrics(BaseModel):
    retrieval_hit_rate_at_k: float = Field(ge=0, le=1)
    citation_provenance_validity: float = Field(ge=0, le=1)


class EvaluationReport(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    status: Literal["pending", "complete"]
    benchmark_version: str
    corpus_document_count: int = Field(ge=0)
    question_count: int = Field(ge=0)
    retrieval_k: int = Field(ge=1)
    generated_at: datetime | None = None
    metrics: EvaluationMetrics | None = None
    note: str
