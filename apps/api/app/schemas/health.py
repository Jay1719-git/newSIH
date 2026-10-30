from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    environment: Literal["SYNTHETIC"] = "SYNTHETIC"
    contract_version: str = "0.1.0"
