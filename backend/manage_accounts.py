"""Local OS/database administrator CLI. Passwords only via hidden terminal prompts."""
import argparse
from getpass import getpass
from uuid import uuid4
import re
import sys
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import get_engine
from models import Account,DriverVehicle,ParentStudent,Vehicle,Student,School
from auth import hasher
from account_admin import revoke_user_sessions


def main():
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    local=commands.add_parser('prepare-local');local.add_argument('--vehicle-id',required=True);local.add_argument('--student-id',required=True)
    password=commands.add_parser('set-password');password.add_argument('username')
    initial=commands.add_parser('activate-initial',help='Set the first password only; never reset an existing password');initial.add_argument('username')
    create=commands.add_parser('create-test',help='Create one synthetic-linked account; refuse existing usernames')
    create.add_argument('username');create.add_argument('--role',required=True,choices=['driver','parent'])
    create.add_argument('--vehicle-id');create.add_argument('--student-id')
    disable=commands.add_parser('disable');disable.add_argument('username')
    args=parser.parse_args()
    with Session(get_engine()) as session:
        if args.command=='create-test':
            if not re.fullmatch(r'[a-z0-9_.@-]{3,100}',args.username):parser.error('Use a lowercase username of 3..100 permitted characters.')
            if session.scalar(select(Account).where(Account.username==args.username)):parser.error('Account already exists; preserved unchanged.')
            if args.role=='driver':
                record=session.get(Vehicle,args.vehicle_id) if args.vehicle_id else None
                if args.student_id or not record or record.input_source!='simulated':parser.error('Driver requires an existing synthetic --vehicle-id only.')
            else:
                record=session.get(Student,args.student_id) if args.student_id else None
                if args.vehicle_id or not record or record.input_source!='simulated' or not record.active:parser.error('Parent requires an active synthetic --student-id only.')
                vehicle=session.get(Vehicle,record.vehicle_id);school=session.get(School,record.school_id)
                if not vehicle or not school or vehicle.input_source!='simulated' or school.input_source!='simulated':parser.error('Student vehicle and school must also be synthetic.')
            if not sys.stdin.isatty():parser.error('Run directly in an interactive terminal for hidden password entry.')
            first=getpass('Initial password (12+ characters; hidden): ');second=getpass('Confirm password (hidden): ')
            if first!=second or not 12<=len(first)<=1024:parser.error('Passwords must match and contain 12..1024 characters.')
            user=Account(id='USER_'+uuid4().hex,username=args.username,role=args.role,password_hash=hasher.hash(first),active=True,demo_only=False,failed_attempts=0)
            session.add(user);session.flush()
            session.add(DriverVehicle(account_id=user.id,vehicle_id=record.id) if args.role=='driver' else ParentStudent(account_id=user.id,student_id=record.id))
            session.commit();print('Test account created with its synthetic relationship; Authenticated operations permitted.');return
        if args.command=='prepare-local':
            vehicle=session.get(Vehicle,args.vehicle_id);student=session.get(Student,args.student_id)
            if not vehicle or not student or vehicle.input_source!='simulated' or student.input_source!='simulated' or student.vehicle_id!=vehicle.id:
                parser.error('Local demonstration accounts require a matching existing synthetic vehicle/student.')
            for role,name in [('administrator','admin.local'),('driver','driver.local'),('parent','parent.local')]:
                user=session.scalar(select(Account).where(Account.username==name))
                if user:
                    print(f'{name}: existing account preserved; use authenticated administration to change links.');continue
                user=Account(id='USER_'+uuid4().hex,username=name,role=role,password_hash='!',active=False,demo_only=False,failed_attempts=0)
                session.add(user);session.flush()
                if role=='driver':session.add(DriverVehicle(account_id=user.id,vehicle_id=vehicle.id))
                if role=='parent':session.add(ParentStudent(account_id=user.id,student_id=student.id))
                print(f'{name}: created LOCKED; set a password privately before login.')
            session.commit();return
        user=session.scalar(select(Account).where(Account.username==args.username.lower()))
        if not user:parser.error('Account not found.')
        if args.command=='activate-initial':
            if user.active or user.password_hash!='!':parser.error('Account already initialized; preserved unchanged. No password reset performed.')
            if not sys.stdin.isatty():parser.error('Run directly in an interactive terminal for hidden password entry.')
        revoke_user_sessions(session,user.id)
        if args.command=='disable':user.active=False
        else:
            first=getpass('New password (12+ characters; hidden): ');second=getpass('Confirm password (hidden): ')
            if first!=second or not 12<=len(first)<=1024:parser.error('Passwords must match and contain 12..1024 characters.')
            user.password_hash=hasher.hash(first);user.active=True;user.failed_attempts=0;user.locked_until=None
        session.commit();print('Account updated; previous login and tracking sessions revoked. No password is printed.')


if __name__=='__main__':main()
