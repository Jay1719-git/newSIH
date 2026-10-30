from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class UploadBatchRequest(BaseModel):
    """Retains current web-client metadata; authorization always uses the token principal."""

    model_config = ConfigDict(extra="ignore")

    filename: str = Field(min_length=1, max_length=255)
    csv_content: str = Field(min_length=1, max_length=5 * 1024 * 1024)
    institution_id: str | None = None
    actor_role: str | None = None
    actor_email: str | None = None
