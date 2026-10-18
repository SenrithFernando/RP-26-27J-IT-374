"""PP1 landmark test adapter, NOT Hasara's API. No paid calls during setup."""
from datetime import date,datetime,timezone,timedelta
from hashlib import sha256
import json
from uuid import uuid4
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field,AwareDatetime,ValidationError,model_validator
from typing import Literal
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import get_engine
from persistence import session_dependency
from models import (Vehicle,School,Student,RouteVersion,Trip,RoutingEvent,LandmarkScenario,LandmarkAttendance,LandmarkBoarding,LandmarkInputEvent,LandmarkDailyPlan)
from planning_state import planning_lock,execution_guard

SCENARIO='MALABE_PP1';PREFIX='MALABE_PP1_';VEHICLE=PREFIX+'VAN_01';DEFAULT_DATE=date(2026,10,19)
VERSION='saferide-routing-provisional/v1'
DEPOT='SALT EduWay, 488/2 Lake Road, Averihena, Hokandara, South, Battaramulla 10118'
SCHOOLS={
 'SCH_A':('Horizon College International','482/B Millennium Dr, Malabe 10115',None,None),
 'SCH_B':("Boys' Model College",'391 Kaduwela Rd, Malabe 10115',6.903543,79.957162)}
PARTICIPANTS=[
 ('TEST_01','Rampe Kitchen, 318 4kaduwela rd, Malabe 10115','SCH_A',True),
 ('TEST_02','Shoe Labz X Enzon, Junction, New Kandy Rd, Malabe','SCH_A',True),
 ('TEST_03','CINEC Campus (Pvt) Ltd, IT Park, Millennium Dr, Malabe','SCH_A',False),
 ('TEST_04',"Datha's Boarding Place, WX7C+M39, Pasan Mawatha, Malabe",'SCH_A',True),
 ('TEST_05','SkyLights 3D Cinema, 471/E Athurugiriya Rd, Malabe','SCH_B',True),
 ('TEST_06','Keells - Pittugala, 296 Kaduwela Rd, Malabe','SCH_B',True),
 ('TEST_07','Sri Lanka Institute of Information Technology, SLIIT Malabe Campus, New Kandy Rd, Malabe 10115','SCH_B',True),
 ('TEST_08','GRAPHIC HEART STAMPS, 255/3, Malabe 10115','SCH_B',True)]
PROVENANCE='Landmark locations with demonstration assignments and test attendance; not student homes, measured trips or physical boarding evidence.'
router=APIRouter(prefix='/daily-plan',tags=['Provisional PP1 landmark scenario'])

class Strict(BaseModel):model_config=ConfigDict(extra='forbid')
class RegistrationLocation(Strict):
    address:str|None=Field(default=None,min_length=1,max_length=500)
    latitude:float|None=Field(default=None,ge=-90,le=90,allow_inf_nan=False)
    longitude:float|None=Field(default=None,ge=-180,le=180,allow_inf_nan=False)
    @model_validator(mode='after')
    def coordinate_pair(self):
        if (self.latitude is None)!=(self.longitude is None):raise ValueError('Both coordinates required together.')
        return self
class AttendanceRecord(Strict):
    student_external_id:str
    service_date:date
    am:Literal['yes','no','unknown']
    pm:Literal['yes','no','unknown']
class BoardingRecord(Strict):
    student_external_id:str
    service_date:date
    direction:Literal['morning']='morning'
    outcome:Literal['boarded','no_show','unknown']
class AssignmentRecord(RegistrationLocation):
    student_external_id:str
    school_external_id:Literal['SCH_A','SCH_B']
    vehicle_external_id:Literal['VAN_01']='VAN_01'
    active:bool=True
class VehicleRecord(RegistrationLocation):
    vehicle_external_id:Literal['VAN_01']
    capacity:int=Field(ge=1,le=20)
class SchoolRecord(RegistrationLocation):
    school_external_id:Literal['SCH_A','SCH_B']
    name:str
    starts_seconds:Literal[27000]=27000
    hard_arrival_seconds:Literal[26100]=26100
    preferred_arrival_seconds:Literal[25500]=25500
    release_seconds:Literal[48600]=48600
    morning_group_service_seconds:Literal[600]=600
    afternoon_group_service_seconds:Literal[900]=900
    boarding_window_seconds:Literal[900]=900
class PolicyRecord(Strict):afternoon_only:Literal['unresolved','allow','deny']
class Envelope(Strict):
    schema_version:Literal['saferide-routing-provisional/v1']
    event_id:str=Field(min_length=1,max_length=128)
    occurred_at:AwareDatetime
    producer:Literal['manual_test','hasara_adapter_provisional']
    provenance:Literal['landmark_test']
    kind:Literal['attendance','boarding','assignment','vehicle','school','policy']
    reason:str=Field(min_length=3,max_length=500)
    records:list[dict]=Field(min_length=1,max_length=20)
class Generation(Strict):
    service_date:date=DEFAULT_DATE
    direction:Literal['morning','afternoon']
    provider:Literal['simulation','ml','google','baseline','unavailable']='simulation'
    departure_seconds:int|None=Field(default=None,ge=0,lt=86400)
class Publication(Strict):
    service_date:date
    direction:Literal['morning','afternoon']
    route_id:str
    review_unresolved_boarding:bool=False
    reason:str=Field(min_length=3,max_length=500)

def scenario_for_vehicle(session,vehicle_id):
    return session.scalar(select(LandmarkScenario).where(LandmarkScenario.vehicle_id==vehicle_id))
def scenario(session):
    row=session.get(LandmarkScenario,SCENARIO)
    if not row:raise HTTPException(404,'Set up the isolated Malabe landmark scenario first.')
    return row
def digest(value):return sha256(json.dumps(value,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()

def setup(session,actor='local_cli'):
    planning_lock(session)
    if session.get(LandmarkScenario,SCENARIO):return {'created':False,'scenario_id':SCENARIO,'vehicle_id':VEHICLE}
    ids=[VEHICLE]+[PREFIX+k for k in SCHOOLS]+[PREFIX+p[0] for p in PARTICIPANTS]
    if session.get(Vehicle,VEHICLE) or any(session.get(School,PREFIX+k) for k in SCHOOLS) or any(session.get(Student,PREFIX+p[0]) for p in PARTICIPANTS):raise HTTPException(409,'Reserved IDs already exist without scenario registration; no records overwritten.')
    session.add(Vehicle(id=VEHICLE,capacity=20,input_source='simulated',start_address=DEPOT,end_address=DEPOT,roster_version=0));session.flush()
    for key,(name,address,lat,lon) in SCHOOLS.items():
        session.add(School(id=PREFIX+key,name=name,address=address,latitude=lat,longitude=lon,location_confirmed=False,location_method='manual',input_source='simulated',morning_deadline_seconds=26100,afternoon_finish_seconds=48600))
    session.flush()
    for key,address,school,pm in PARTICIPANTS:
        session.add(Student(id=PREFIX+key,name=key+' — landmark test',home_id=PREFIX+key+'_LOCATION',home_address=address,school_id=PREFIX+school,vehicle_id=VEHICLE,input_source='simulated',location_confirmed=False,location_method='manual',active=True))
    session.flush()
    manifest={'name':'Malabe landmark field test','timezone':'Asia/Colombo','provenance':PROVENANCE,'contract_version':VERSION,'afternoon_only':'unresolved','supplied_depot_address':DEPOT,'supplied_school_addresses':{k:v[1] for k,v in SCHOOLS.items()},'supplied_participant_addresses':{p[0]:p[1] for p in PARTICIPANTS},'coordinate_origins':{'SCH_B':'user_supplied_pending_map_confirmation'},'student_ids':[PREFIX+p[0] for p in PARTICIPANTS],'school_ids':[PREFIX+k for k in SCHOOLS]}
    session.add(LandmarkScenario(id=SCENARIO,vehicle_id=VEHICLE,default_date=DEFAULT_DATE,policy=manifest));session.flush()
    stamp=datetime.now(timezone.utc);event_id='MALABE_SETUP_v1'
    payload={'schema_version':VERSION,'kind':'setup','provenance':'landmark_test','occurred_at':stamp.isoformat(),'initial_date':DEFAULT_DATE.isoformat()}
    session.add(LandmarkInputEvent(event_id=event_id,scenario_id=SCENARIO,payload_hash=digest(payload),payload=payload,actor_id=actor,received_at=stamp))
    for key,_,_,pm in PARTICIPANTS:session.add(LandmarkAttendance(scenario_id=SCENARIO,service_date=DEFAULT_DATE,student_id=PREFIX+key,am='yes',pm='yes' if pm else 'no',occurred_at=stamp,event_id=event_id))
    session.commit()
    return {'created':True,'scenario_id':SCENARIO,'vehicle_id':VEHICLE,'provenance':PROVENANCE}

def attendance_snapshot(session,sc,day,direction):
    people=session.scalars(select(Student).where(Student.id.in_(sc.policy['student_ids'])).order_by(Student.id)).all()
    rows=[];selected=[];unknown=[];review=[];afternoon_only=[]
    for p in people:
        a=session.get(LandmarkAttendance,(sc.id,day,p.id));b=session.get(LandmarkBoarding,(sc.id,day,p.id))
        am=a.am if a else 'unknown';pm=a.pm if a else 'unknown';evidence=b.outcome if b else 'unknown'
        assigned=p.active and p.vehicle_id==sc.vehicle_id
        decision=am if direction=='morning' else pm
        eligible=assigned and decision=='yes';reason=None
        if assigned and decision=='unknown':unknown.append(p.id)
        if direction=='afternoon' and eligible:
            if evidence=='no_show':eligible=False;reason='Confirmed manual-test morning no-show excludes PM under test policy.'
            elif am=='unknown':unknown.append(p.id)
            elif am=='no':
                if sc.policy['afternoon_only']=='deny':eligible=False;reason='Explicit test-only afternoon-only policy denies transport.'
                elif sc.policy['afternoon_only']=='unresolved':afternoon_only.append(p.id)
            if eligible and evidence=='unknown':review.append(p.id)
        if eligible:selected.append(p)
        rows.append({'student_id':p.id,'external_id':p.id.removeprefix(PREFIX),'am':am,'pm':pm,'morning_evidence':evidence,'eligible':eligible,'exclusion_reason':reason,'attendance_event_id':a.event_id if a else None,'boarding_event_id':b.event_id if b else None})
    return selected,{'rows':rows,'unknown_attendance':sorted(set(unknown)),'unresolved_boarding':review,'unresolved_afternoon_only':afternoon_only,'provenance':PROVENANCE}

def fingerprint(session,sc,day,direction):
    from planning_orchestration import columns
    people,snap=attendance_snapshot(session,sc,day,direction)
    # Direction-specific evidence; PM edits do not invalidate AM, dates never bleed.
    rows=[{k:r[k] for k in (['student_id','am'] if direction=='morning' else ['student_id','pm'] if r['pm']=='no' else ['student_id','am','pm','morning_evidence'])} for r in snap['rows']]
    return digest({'attendance':rows,'vehicle':columns(session.get(Vehicle,sc.vehicle_id)),
        'students':[columns(s) for s in session.scalars(select(Student).where(Student.id.in_(sc.policy['student_ids'])).order_by(Student.id))],
        'schools':[columns(session.get(School,k)) for k in sc.policy['school_ids']],
        'afternoon_only':sc.policy['afternoon_only'] if direction=='afternoon' else None})

def prepare_context(session,sc,request):
    selected,snapshot=attendance_snapshot(session,sc,request.service_date,request.direction)
    return selected,{'scenario_id':sc.id,'name':sc.policy['name'],'provenance':PROVENANCE,'contract_version':VERSION,
        'attendance':snapshot,'fingerprint':fingerprint(session,sc,request.service_date,request.direction),'policy':sc.policy}

def attach_plan(session,sc,version):
    key=(sc.id,version.service_date,version.direction);state=session.get(LandmarkDailyPlan,key)
    if not state:state=LandmarkDailyPlan(scenario_id=sc.id,service_date=version.service_date,direction=version.direction);session.add(state)
    state.route_id=version.id;state.publication='draft';state.review={};session.flush()

def route_freshness(session,route):
    from zoneinfo import ZoneInfo
    sc=scenario_for_vehicle(session,route.vehicle_id)
    if not sc:return None
    state=session.get(LandmarkDailyPlan,(sc.id,route.service_date,route.direction))
    matches=bool(state and state.route_id==route.id and route.input_snapshot.get('daily',{}).get('fingerprint')==fingerprint(session,sc,route.service_date,route.direction))
    expired=route.service_date<datetime.now(ZoneInfo('Asia/Colombo')).date()
    return {'roster_version':route.roster_version,'current_roster_version':session.get(Vehicle,route.vehicle_id).roster_version,'is_current':matches and not expired and route.feasibility_status=='feasible' and route.execution_status=='pre_trip',
        'planning_status':'locked_'+route.execution_status if route.execution_status!='pre_trip' else 'stale' if not matches or expired else route.feasibility_status,'planning_errors':route.result.get('errors',[]) if matches else ['Dated attendance/assignment/location inputs changed; regenerate the affected pre-trip plan.'],
        'trigger_event_id':route.trigger_event_id,'trigger_event':route.trigger_event_type,'execution_status':route.execution_status,'comparison':{}}

def regenerate(session,sc,days,directions=('morning','afternoon')):
    from route_service import generate_and_store
    from route_schemas import GenerateRouteRequest
    results=[]
    for day in sorted(set(days)):
        for direction in directions:
            state=session.get(LandmarkDailyPlan,(sc.id,day,direction));last=session.get(RouteVersion,state.route_id) if state and state.route_id else None
            if last and last.input_snapshot.get('daily',{}).get('fingerprint')==fingerprint(session,sc,day,direction):continue
            if execution_guard(session,sc.vehicle_id,direction,day):
                if state:state.publication='stale'
                results.append({'direction':direction,'service_date':str(day),'status':'deferred_active_snapshot'});continue
            settings=dict(last.request_settings) if last else dict(vehicle_id=sc.vehicle_id,direction=direction,departure_seconds=21600 if direction=='morning' else 48600,include_geometry=False)
            settings['service_date']=day
            try:
                with session.begin_nested():value=generate_and_store(session,GenerateRouteRequest(**settings),commit=False,trigger_event_type='dated_landmark_input')
                results.append({'direction':direction,'service_date':str(day),'route_id':value['route_id'],'status':value['feasibility_status']})
            except Exception:
                state=session.get(LandmarkDailyPlan,(sc.id,day,direction))
                if state:state.publication='stale'
                results.append({'direction':direction,'service_date':str(day),'status':'routing_failed_inputs_saved'})
    session.commit();return results

def import_event(session,envelope,actor):
    planning_lock(session);sc=scenario(session);body=envelope.model_dump(mode='json');hashed=digest(body)
    old=session.get(LandmarkInputEvent,envelope.event_id)
    if old:
        if old.payload_hash!=hashed:raise HTTPException(409,'Event ID reused with different content.')
        return {'duplicate':True,'event_id':old.event_id,'regenerated':[]}
    if envelope.occurred_at>datetime.now(timezone.utc)+timedelta(seconds=30):raise HTTPException(422,'Event timestamp implausibly future.')
    types={'attendance':AttendanceRecord,'boarding':BoardingRecord,'assignment':AssignmentRecord,'vehicle':VehicleRecord,'school':SchoolRecord,'policy':PolicyRecord}
    try:records=[types[envelope.kind].model_validate(r) for r in envelope.records]
    except ValidationError:raise HTTPException(422,'Invalid provisional contract record; check required fields and enums.') from None
    days=set();global_change=False;directions=('morning','afternoon');changed=False;seen=set()
    for record in records:
        identity=getattr(record,'student_external_id',getattr(record,'school_external_id',getattr(record,'vehicle_external_id','policy')))
        key=(str(getattr(record,'service_date','global')),identity)
        if key in seen:raise HTTPException(422,'Duplicate entity/date in one event.')
        seen.add(key)
        if hasattr(record,'student_external_id') and PREFIX+record.student_external_id not in sc.policy['student_ids']:raise HTTPException(422,'Unknown scenario participant; historical fixtures cannot be imported.')
        if envelope.kind in ('attendance','boarding'):
            day=record.service_date;sid=PREFIX+record.student_external_id;model=LandmarkAttendance if envelope.kind=='attendance' else LandmarkBoarding
            row=session.get(model,(sc.id,day,sid));values={k:getattr(record,k) for k in (['am','pm'] if model is LandmarkAttendance else ['outcome'])}
            if row and envelope.occurred_at<=row.occurred_at:continue
            if not row:row=model(scenario_id=sc.id,service_date=day,student_id=sid);session.add(row)
            if any(getattr(row,k,None)!=v for k,v in values.items()):changed=True;days.add(day)
            for k,v in values.items():setattr(row,k,v)
            row.occurred_at=envelope.occurred_at;row.event_id=envelope.event_id
            if model is LandmarkBoarding:directions=('afternoon',)
        else:
            # Global projection timestamps prevent late imports reverting assignments.
            times=dict(sc.policy.get('import_times',{}));timekey=envelope.kind+':'+identity
            if timekey in times and envelope.occurred_at<=datetime.fromisoformat(times[timekey]):continue
            times[timekey]=envelope.occurred_at.isoformat();sc.policy={**sc.policy,'import_times':times}
            if envelope.kind=='assignment':
                p=session.get(Student,PREFIX+record.student_external_id)
                values={'school_id':PREFIX+record.school_external_id,'vehicle_id':sc.vehicle_id,'active':record.active}
                if any(getattr(p,k)!=v for k,v in values.items()):changed=True;global_change=True
                for k,v in values.items():setattr(p,k,v)
            elif envelope.kind=='vehicle':
                v=session.get(Vehicle,sc.vehicle_id)
                if v.capacity!=record.capacity:v.capacity=record.capacity;changed=True;global_change=True
            elif envelope.kind=='school':
                if record.name!=SCHOOLS[record.school_external_id][0]:raise HTTPException(422,'School mapping is fixed: SCH_A Horizon, SCH_B Boys Model.')
            elif sc.policy['afternoon_only']!=record.afternoon_only:
                sc.policy={**sc.policy,'afternoon_only':record.afternoon_only};changed=True;global_change=True
            if isinstance(record,RegistrationLocation) and (record.address is not None or record.latitude is not None):
                target=session.get(Student,PREFIX+record.student_external_id) if envelope.kind=='assignment' else session.get(School,PREFIX+record.school_external_id) if envelope.kind=='school' else session.get(Vehicle,sc.vehicle_id)
                prefixes=['home_'] if envelope.kind=='assignment' else [''] if envelope.kind=='school' else ['start_','end_']
                for prefix in prefixes:
                    for name in ['address','latitude','longitude']:
                        value=getattr(record,name)
                        if value is not None and getattr(target,prefix+name)!=value:
                            setattr(target,prefix+name,value);changed=True;global_change=True
                            setattr(target,{'home_':'location_confirmed','':'location_confirmed','start_':'start_confirmed','end_':'end_confirmed'}[prefix],False)
                            setattr(target,{'home_':'location_method','':'location_method','start_':'start_method','end_':'end_method'}[prefix],'manual')
                # Import coordinates are explicitly unconfirmed; admin pin review is separate.
    session.add(LandmarkInputEvent(event_id=envelope.event_id,scenario_id=sc.id,payload_hash=hashed,payload=body,actor_id=actor,received_at=datetime.now(timezone.utc)))
    if global_change:
        session.get(Vehicle,sc.vehicle_id).roster_version+=1
        days.update(session.scalars(select(LandmarkDailyPlan.service_date).where(LandmarkDailyPlan.scenario_id==sc.id)))
        days.add(sc.default_date)
    # Reuse the durable existing recovery worker, including disconnect/restart.
    routing_event_id=None
    if changed:
        routing_event_id='EVENT_'+uuid4().hex
        for day in days:
            for direction in directions:
                state=session.get(LandmarkDailyPlan,(sc.id,day,direction))
                if not state:session.add(LandmarkDailyPlan(scenario_id=sc.id,service_date=day,direction=direction,publication='draft',review={}))
        session.add(RoutingEvent(id=routing_event_id,event_type='landmark_'+envelope.kind,entity_id=sc.id,request_key='landmark:'+digest(envelope.event_id),payload_hash=hashed,affected_vehicles={sc.vehicle_id:session.get(Vehicle,sc.vehicle_id).roster_version},record_snapshot={'external_event_id':envelope.event_id},before_routes={},status='pending',outcome={}))
    # Input + pending event commit together; failed generation cannot erase either.
    session.commit()
    from planning_orchestration import process_event_safe
    routing=process_event_safe(session,routing_event_id) if routing_event_id else {'plans':[]}
    return {'duplicate':False,'event_id':envelope.event_id,'changed':changed,'routing':routing,'regenerated':[{**p,'status':p.get('generation_status')} for p in routing.get('plans',[])]}

def publication_blockers(session,sc,day,direction,route):
    _,snap=attendance_snapshot(session,sc,day,direction);errors=[]
    if snap['unknown_attendance']:errors.append('Unknown dated attendance must be explicitly resolved yes/no.')
    if snap['unresolved_afternoon_only']:errors.append('Afternoon-only test policy is unresolved; configure allow/deny explicitly.')
    if not route or route.vehicle_id!=sc.vehicle_id or route.feasibility_status!='feasible' or not route_freshness(session,route)['is_current']:errors.append('A current feasible dated route with confirmed locations is required.')
    return errors,snap

@router.post('/setup')
def setup_api(request:Request,session:Session=Depends(session_dependency)):return setup(session,request.state.principal.user.id)
@router.post('/import')
def import_api(body:Envelope,request:Request,session:Session=Depends(session_dependency)):return import_event(session,body,request.state.principal.user.id)
@router.get('')
def read_daily(service_date:date=DEFAULT_DATE,session:Session=Depends(session_dependency)):
    from persistence import StudentRecord,SchoolRecord as PersistedSchool,VehicleRecord as PersistedVehicle
    from route_service import serialize_version
    sc=scenario(session);plans={};counts={}
    for direction in ('morning','afternoon'):
        people,snap=attendance_snapshot(session,sc,service_date,direction);counts[direction]=len(people)
        state=session.get(LandmarkDailyPlan,(sc.id,service_date,direction));r=session.get(RouteVersion,state.route_id) if state and state.route_id else None
        blockers,_=publication_blockers(session,sc,service_date,direction,r)
        published=state.publication if state else 'not_generated'
        if r and r.input_snapshot.get('daily',{}).get('fingerprint')!=fingerprint(session,sc,service_date,direction):published='stale'
        plans[direction]={'route':serialize_version(session,r) if r else None,'attendance':snap,'publication':published,'review':state.review if state else {},'publication_blockers':blockers}
    return {'scenario_id':sc.id,'name':sc.policy['name'],'service_date':str(service_date),'default_date':str(sc.default_date),'timezone':'Asia/Colombo','provenance':PROVENANCE,'policy':sc.policy,'counts':counts,'plans':plans,
        'vehicle':PersistedVehicle.model_validate(session.get(Vehicle,sc.vehicle_id)).model_dump(mode='json'),
        'schools':[PersistedSchool.model_validate(session.get(School,k)).model_dump(mode='json') for k in sc.policy['school_ids']],
        'students':[StudentRecord.model_validate(p).model_dump(mode='json') for p in session.scalars(select(Student).where(Student.id.in_(sc.policy['student_ids'])).order_by(Student.id))]}
@router.post('/generate')
def generate_daily(body:Generation,session:Session=Depends(session_dependency)):
    from route_service import generate_and_store
    from route_schemas import GenerateRouteRequest
    sc=scenario(session)
    return generate_and_store(session,GenerateRouteRequest(vehicle_id=sc.vehicle_id,service_date=body.service_date,direction=body.direction,departure_seconds=body.departure_seconds if body.departure_seconds is not None else 21600 if body.direction=='morning' else 48600,provider=body.provider,include_geometry=False))
@router.post('/publish')
def publish(body:Publication,request:Request,session:Session=Depends(session_dependency)):
    planning_lock(session);sc=scenario(session);state=session.get(LandmarkDailyPlan,(sc.id,body.service_date,body.direction));route=session.get(RouteVersion,body.route_id)
    errors,snap=publication_blockers(session,sc,body.service_date,body.direction,route)
    if not state or state.route_id!=body.route_id or not route or route.vehicle_id!=sc.vehicle_id or route.service_date!=body.service_date or route.direction!=body.direction:errors.append('Selected dated plan/version does not match.')
    if snap['unresolved_boarding'] and not body.review_unresolved_boarding:errors.append('Explicit review of unknown morning boarding evidence is required for PM publication.')
    if errors:raise HTTPException(409,' '.join(errors))
    audit={'schema_version':VERSION,'event_id':'PUB_'+uuid4().hex,'kind':'publication','service_date':str(body.service_date),'direction':body.direction,'route_id':route.id,'review_unresolved_boarding':body.review_unresolved_boarding,'unknown_student_ids':snap['unresolved_boarding'],'reason':body.reason,'recorded_at':datetime.now(timezone.utc).isoformat()}
    session.add(LandmarkInputEvent(event_id=audit['event_id'],scenario_id=sc.id,payload_hash=digest(audit),payload=audit,actor_id=request.state.principal.user.id,received_at=datetime.now(timezone.utc)))
    state.publication='published';state.review=audit;session.commit();return {'publication':'published','route_id':route.id,'review':audit}
