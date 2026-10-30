from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class DuplicateDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal[
        "CONFIRMED_DUPLICATE",
        "DISTINCT_STUDENTS",
        "INSUFFICIENT_EVIDENCE",
        "ESCALATED",
    ]
