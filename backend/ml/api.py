from datetime import datetime
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from ml.predictor import ModelUnavailable, predictor

router = APIRouter(prefix='/ml', tags=['Synthetic-data ML'])


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    origin_id: str = Field(min_length=1, max_length=128)
    destination_id: str = Field(min_length=1, max_length=128)
    departure_timestamp: datetime
    distance_m: float = Field(ge=0, le=40_100_000, allow_inf_nan=False)
    weather_flag: Literal[0, 1] | None = None

    @field_validator('departure_timestamp')
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None or value.utcoffset() is None: raise ValueError('Timestamp must include a UTC offset.')
        return value

    @field_validator('weather_flag', mode='before')
    @classmethod
    def weather_required_values(cls, value):
        if value is not None and (type(value) is not int or value not in (0, 1)): raise ValueError('Use integer 0, integer 1 or null for missing weather.')
        return value


@router.get('/status')
def status(): return predictor.status()


@router.post('/predict')
def predict(payload: PredictionRequest):
    try: return predictor.predict_many([payload.model_dump()])[0]
    except ModelUnavailable as error: raise HTTPException(503, str(error)) from None
    except ValueError as error: raise HTTPException(422, str(error)) from None
