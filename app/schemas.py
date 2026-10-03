from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class IrisFeatures(BaseModel):
    sepal_length: float = Field(gt=0, le=10)
    sepal_width: float = Field(gt=0, le=10)
    petal_length: float = Field(gt=0, le=10)
    petal_width: float = Field(gt=0, le=10)


class PredictRequest(BaseModel):
    instances: list[IrisFeatures] = Field(min_length=1, max_length=100)


class PredictResponse(BaseModel):
    model_uri: str
    model_version: str
    predictions: list[str]


class V2Input(BaseModel):
    name: str = "input-0"
    shape: list[int]
    datatype: str = "FP64"
    data: list[list[float]]

    @field_validator("data")
    @classmethod
    def validate_four_features(cls, rows: list[list[float]]) -> list[list[float]]:
        if not rows or any(len(row) != 4 for row in rows):
            raise ValueError("Each input row must contain exactly four Iris features")
        return rows


class V2InferRequest(BaseModel):
    id: str | None = None
    inputs: list[V2Input] = Field(min_length=1, max_length=1)
