"""Authenticated administrator-only measured evidence export, no file writes."""
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy.orm import Session
from persistence import session_dependency
from data_provenance import validate_measured_observations
router=APIRouter(tags=['Protected exports'])


class ExportInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    observations:list[dict]=Field(max_length=1000)


@router.post('/exports/measured-observations')
def measured_export(body:ExportInput,session:Session=Depends(session_dependency)):
    try:return {'observations':validate_measured_observations(session,body.observations)}
    except ValueError as error:raise HTTPException(422,str(error)) from None
