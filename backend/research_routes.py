"""Isolated ordered adult research routes; no school solver, roster or windows."""
from datetime import date,datetime,time,timedelta,timezone
from zoneinfo import ZoneInfo
from uuid import uuid4
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field,model_validator
from sqlalchemy import select,func,case
from sqlalchemy.orm import Session
from persistence import session_dependency
from models import RouteVersion,RouteStop,Vehicle,Account,DriverVehicle,Trip
from planning_state import planning_lock
from arrivals import configured_settings,distance_m

router=APIRouter(prefix='/research-routes',tags=['Isolated adult research routes'])
VEHICLE='MALABE_PP1_VAN_01'
LANDMARKS={
 'A':{'name':'SALT EduWay — reviewed research stopping point','place_address':'SALT EduWay, 488/2 Lake Road, Averihena, Hokandara, South, Battaramulla 10118','stopping_address':'25 Wewa Rd, Sri Jayawardenepura Kotte 10115','instruction':'Two supplied addresses may differ. Confirm the intended vehicle stopping coordinate manually.'},
 'B':{'name':'CEB Battaramulla landmark','place_address':'CEB Battaramulla 132/33KV Grid, WX66+P9G, Wewa Rd, Sri Jayawardenepura Kotte 10115','stopping_address':'','instruction':'Confirm a permitted public roadside stopping point outside the electrical facility; not the building centroid.'},
 'C':{'name':'The Best "B" bakery','place_address':'The Best "B", WX47+GPP, Malabe','stopping_address':'','instruction':'Confirm the accessible stopping point.'}}

def is_research(route):return bool(route and route.input_snapshot.get('research_journey',{}).get('schema')=='adult-ordered-route/v1')
def latest(session,vehicle_id,day):
 return session.scalar(select(RouteVersion).where(RouteVersion.vehicle_id==vehicle_id,RouteVersion.service_date==day,
  RouteVersion.input_snapshot['research_journey'].is_not(None)).order_by(RouteVersion.version.desc()).limit(1))

class Pin(BaseModel):
 model_config=ConfigDict(extra='forbid')
 latitude:float=Field(ge=-90,le=90,allow_inf_nan=False)
 longitude:float=Field(ge=-180,le=180,allow_inf_nan=False)
 manually_confirmed:bool=Field(strict=True)
 permitted_public_stop:bool=Field(strict=True)
 stopping_note:str=Field(min_length=10,max_length=1000)
 reviewed_address:str=Field(default='',max_length=1000)
 location_method:Literal['manual','google','manual_correction']='manual'

class Preparation(BaseModel):
 model_config=ConfigDict(extra='forbid')
 service_date:date
 departure_seconds:int=Field(ge=0,lt=86400)
 travel_mode:Literal['driving','walking','bicycling']
 driver_id:str=Field(min_length=1,max_length=64)
 operator_id:str=Field(min_length=1,max_length=64)
 separate_people_confirmed:bool=Field(strict=True)
 adults_only_confirmed:bool=Field(strict=True)
 reason:str=Field(min_length=10,max_length=1000)
 pins:dict[str,Pin]
 @model_validator(mode='after')
 def validate_pins(self):
  if set(self.pins)!={'A','B','C'}:raise ValueError('Exactly A, B and C pins are required; return A reuses the same reviewed point.')
  if not all(p.manually_confirmed and p.permitted_public_stop for p in self.pins.values()):raise ValueError('Manually confirm every permitted accessible stopping pin.')
  if not self.separate_people_confirmed or not self.adults_only_confirmed or self.driver_id==self.operator_id:raise ValueError('Adult-only confirmation and separate driver/operator are required.')
  radius=configured_settings()['exit_radius_metres']
  for a,b in [('A','B'),('B','C'),('C','A')]:
   x,y=self.pins[a],self.pins[b]
   if distance_m(x.latitude,x.longitude,y.latitude,y.longitude)<=2*radius:raise ValueError(f'{a} → {b} must be distinct and separated by more than {2*radius:g} m.')
  return self

def participants_valid(session,meta):
 driver=session.get(Account,meta['driver_id']);operator=session.get(Account,meta['operator_id'])
 return bool(driver and operator and driver.active and operator.active and not driver.demo_only and not operator.demo_only and
  driver.role=='driver' and operator.role=='administrator' and driver.id!=operator.id and
  session.get(DriverVehicle,(driver.id,VEHICLE)))

def require_research_plan(session,route,starting=False):
 meta=route.input_snapshot['research_journey']
 now=datetime.now(ZoneInfo('Asia/Colombo'))
 if route.execution_status!='pre_trip' or latest(session,route.vehicle_id,route.service_date).id!=route.id:raise HTTPException(409,'Use the latest unstarted reviewed research version. Active/completed routes are immutable.')
 if route.service_date<now.date() or (starting and route.service_date!=now.date()):raise HTTPException(409,'Research starts require today in Asia/Colombo; no backdating.')
 if not participants_valid(session,meta):raise HTTPException(409,'Assigned driver and separate active administrator/operator must remain authorized.')
 if starting and datetime.combine(route.service_date,time(),ZoneInfo('Asia/Colombo'))+timedelta(seconds=route.departure_seconds)<now-timedelta(minutes=10):
  raise HTTPException(409,'Research departure is over 10 minutes past. Save a reviewed version with a later departure before starting; no backdated start.')

def save_route(session,body,actor):
 planning_lock(session)
 now=datetime.now(ZoneInfo('Asia/Colombo'))
 depart=datetime.combine(body.service_date,time(),ZoneInfo('Asia/Colombo'))+timedelta(seconds=body.departure_seconds)
 if depart<=now:raise HTTPException(422,'Choose a future departure in Asia/Colombo; date/time remain editable.')
 meta={'schema':'adult-ordered-route/v1','ordered_keys':['A','B','C','A'],'driver_id':body.driver_id,'operator_id':body.operator_id,
  'separate_people_confirmed':True,'adults_only_confirmed':True,'reviewed_by':actor,'reason':body.reason,'travel_mode':body.travel_mode,
  'reviewed_at':datetime.now(timezone.utc).isoformat(),'landmarks':LANDMARKS,'pins':body.model_dump(mode='json')['pins']}
 if not participants_valid(session,meta):raise HTTPException(422,'Choose an assigned active driver and a different active administrator to operate the phone.')
 if session.scalar(select(Trip.id).where(Trip.vehicle_id==VEHICLE,Trip.state=='ACTIVE').limit(1)):raise HTTPException(409,'An active trip must finish before preparing a replacement research journey.')
 vehicle=session.get(Vehicle,VEHICLE)
 if not vehicle:raise HTTPException(404,'Initialize the existing authorized Malabe vehicle first.')
 previous=latest(session,VEHICLE,body.service_date)
 if previous and previous.execution_status=='pre_trip' and previous.input_snapshot['research_journey']['pins']==meta['pins'] and previous.input_snapshot['research_journey']['travel_mode']==body.travel_mode and previous.departure_seconds==body.departure_seconds and previous.input_snapshot['research_journey']['driver_id']==body.driver_id and previous.input_snapshot['research_journey']['operator_id']==body.operator_id and previous.input_snapshot['research_journey']['reason']==body.reason:return previous
 version=(session.scalar(select(func.max(RouteVersion.version)).where(RouteVersion.vehicle_id==VEHICLE,RouteVersion.direction=='afternoon')) or 0)+1
 locations={f'RESEARCH_{k}':{'latitude':p.latitude,'longitude':p.longitude,'confirmed':True,'input_source':'simulated','location_method':p.location_method,'address':p.reviewed_address or p.stopping_note} for k,p in body.pins.items()}
 result={'feasibility_status':'feasible','errors':[],'research_journey':meta,'route_kind':'adult_research','student_count':0,'capacity':vehicle.capacity,
  'assignment_policy':'No passenger roster. Explicit fixed A → B → C → A research order; no optimizer or reordering.',
  'distance_metres':None,'driving_seconds':None,'service_seconds':0,'waiting_seconds':None,'total_duration_seconds':None,
  'solver_runtime_seconds':None,'solver_status':'not_run_fixed_research_order','optimality':'No optimization or optimum claimed.',
  'provider_source':{'provider':'unavailable','duration_source':'unavailable','distance_is_approximate':True,'description':'Research sequence only; travel times/ETAs unavailable. No provider called.'},
  'road_geometry':{'status':'unavailable','reason':'Stop sequence — not a road route. No paid geometry requested.'},'end_policy':'explicit_return_A'}
 row=RouteVersion(id='RROUTE_'+uuid4().hex,vehicle_id=VEHICLE,direction='afternoon',version=version,roster_version=vehicle.roster_version,
  trigger_event_type='adult_research_review',execution_status='pre_trip',service_date=body.service_date,departure_seconds=body.departure_seconds,
  feasibility_status='feasible',created_at=datetime.now(timezone.utc),request_settings={'provider':'unavailable','research_only':True},
  input_snapshot={'research_journey':meta,'research_locations':locations,'students':[],'schools':{}},result=result)
 session.add(row);session.flush()
 for n,key in enumerate(meta['ordered_keys'],1):
  loc=locations['RESEARCH_'+key];action='start' if n==1 else 'end' if n==4 else 'pickup'
  details={'sequence':n,'event_id':f'RESEARCH_{key}_OCCURRENCE_{n}','location_id':'RESEARCH_'+key,'name':LANDMARKS[key]['name'],
   'occurrence':n,'research_key':key,'action':action,'student_id':None,'student_ids':[],'school_id':None,
   'latitude':loc['latitude'],'longitude':loc['longitude'],'address':loc['address'],'input_source':'simulated','location_method':loc['location_method'],
   'arrival':None,'eta':None,'departure':depart.isoformat() if n==1 else None,'arrival_seconds':None,'eta_seconds':None,'departure_seconds':None,
   'service_seconds':0,'waiting_seconds':0,'driving_seconds_from_previous':None,'distance_metres_from_previous':None,'load_before':0,'load_after':0,
   'travel_source':{'source':'unavailable'},'research_visit':True}
  session.add(RouteStop(route_id=row.id,sequence=n,action=action,student_id=None,location_id=details['location_id'],latitude=loc['latitude'],longitude=loc['longitude'],eta_seconds=None,details=details))
 session.flush();return row

@router.get('/template')
def template(request:Request):
 from research_observations import administrator
 administrator(request);return {'vehicle_id':VEHICLE,'landmarks':LANDMARKS,'order':['A','B','C','A'],'coordinates':None,'travel_mode':None}

@router.post('')
def prepare(body:Preparation,request:Request,session:Session=Depends(session_dependency)):
 from research_observations import administrator
 from route_service import serialize_version
 row=save_route(session,body,administrator(request));session.commit();return serialize_version(session,row)

@router.get('/current')
def current(request:Request,vehicle_id:str,service_date:date,session:Session=Depends(session_dependency)):
 from auth import scope_vehicle,scope_trip,scope_route
 from route_service import serialize_version
 from trips import serialize_trip
 p=request.state.principal
 if p.login.mode!='real' or p.user.role not in ('administrator','driver'):raise HTTPException(403,'Authenticated driver/admin only.')
 scope_vehicle(session,p,vehicle_id)
 row=latest(session,vehicle_id,service_date)
 if row:scope_route(session,p,row.id)
 trip=session.scalar(select(Trip).join(RouteVersion,Trip.route_id==RouteVersion.id).where(Trip.vehicle_id==vehicle_id,
  RouteVersion.input_snapshot['research_journey'].is_not(None),RouteVersion.service_date==service_date)
  .order_by(case((Trip.state=='ACTIVE',0),else_=1),Trip.created_at.desc()).limit(1))
 if trip:scope_trip(session,p,trip.id)
 return {'publication_status':'reviewed_research' if row else 'not_prepared','published_route':serialize_version(session,row) if row else None,
  'trip':serialize_trip(session,trip) if trip else None}
