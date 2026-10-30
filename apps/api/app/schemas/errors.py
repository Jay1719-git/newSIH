from pydantic import BaseModel, ConfigDict


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str | None = None
    reason: str


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    request_id: str
    details: list[ErrorDetail]


class ApiErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorBody
