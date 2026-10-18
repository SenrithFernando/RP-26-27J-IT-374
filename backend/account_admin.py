"""Administrator-only account/relationship API. No passwords or hashes returned."""
from uuid import uuid4
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy import select,update,delete
from sqlalchemy.orm import Session
from models import Account,DriverVehicle,ParentStudent,TrackingSession,LoginSession,Vehicle,Student
from persistence import session_dependency
from auth import now,hasher
router=APIRouter(tags=['Account administration'])


@router.get('/auth/admin/accounts')
def accounts(session:Session=Depends(session_dependency)):
    return [{'id':row.id,'username':row.username,'role':row.role,'active':row.active,'demo_only':row.demo_only,
        'vehicle_ids':session.scalars(select(DriverVehicle.vehicle_id).where(DriverVehicle.account_id==row.id)).all(),
        'student_ids':session.scalars(select(ParentStudent.student_id).where(ParentStudent.account_id==row.id)).all()}
        for row in session.scalars(select(Account).order_by(Account.username)).all()]


class NewAccount(BaseModel):
    model_config=ConfigDict(extra='forbid')
    username:str=Field(pattern='^[a-z0-9_.@-]{3,100}$')
    role:str=Field(pattern='^(administrator|driver|parent)$')
    password:str=Field(min_length=12,max_length=1024)
    demo_only:bool=False


@router.post('/auth/admin/accounts',status_code=201)
def create(body:NewAccount,session:Session=Depends(session_dependency)):
    if session.scalar(select(Account.id).where(Account.username==body.username)):raise HTTPException(409,'Username exists.')
    row=Account(id='USER_'+uuid4().hex,username=body.username,role=body.role,password_hash=hasher.hash(body.password),
        active=True,demo_only=body.demo_only,failed_attempts=0)
    session.add(row);session.commit();return {'id':row.id,'username':row.username,'role':row.role}


class Links(BaseModel):
    model_config=ConfigDict(extra='forbid')
    ids:list[str]=Field(max_length=100)


def revoke_user_sessions(session,user_id):
    session.scalar(select(Account).where(Account.id==user_id).with_for_update())
    # Ascending login locks serialize authorization changes with concurrent uploads.
    logins=session.scalars(select(LoginSession).where(LoginSession.account_id==user_id).order_by(LoginSession.id).with_for_update()).all()
    for login in logins:login.revoked_at=now()
    session.execute(update(TrackingSession).where(TrackingSession.login_session_id.in_([s.id for s in logins]),TrackingSession.revoked_at.is_(None)).values(revoked_at=now()))


@router.put('/auth/admin/accounts/{user_id}/vehicles')
def vehicle_links(user_id:str,body:Links,session:Session=Depends(session_dependency)):
    user=session.get(Account,user_id)
    if not user or user.role!='driver':raise HTTPException(422,'Select a driver account.')
    if any(not session.get(Vehicle,id) for id in body.ids):raise HTTPException(422,'Unknown vehicle.')
    revoke_user_sessions(session,user_id)
    session.execute(delete(DriverVehicle).where(DriverVehicle.account_id==user_id))
    for id in set(body.ids):session.add(DriverVehicle(account_id=user_id,vehicle_id=id))
    session.commit();return {'assigned_vehicle_ids':sorted(set(body.ids)),'sessions_revoked':True}


@router.put('/auth/admin/accounts/{user_id}/students')
def student_links(user_id:str,body:Links,session:Session=Depends(session_dependency)):
    user=session.get(Account,user_id)
    if not user or user.role!='parent':raise HTTPException(422,'Select a parent account.')
    if any(not session.get(Student,id) for id in body.ids):raise HTTPException(422,'Unknown student.')
    revoke_user_sessions(session,user_id)
    session.execute(delete(ParentStudent).where(ParentStudent.account_id==user_id))
    for id in set(body.ids):session.add(ParentStudent(account_id=user_id,student_id=id))
    session.commit();return {'linked_student_ids':sorted(set(body.ids)),'sessions_revoked':True}


@router.post('/auth/admin/accounts/{user_id}/revoke')
def revoke_account(user_id:str,session:Session=Depends(session_dependency)):
    if not session.get(Account,user_id):raise HTTPException(404,'Account not found.')
    revoke_user_sessions(session,user_id);session.commit();return {'sessions_revoked':True}
