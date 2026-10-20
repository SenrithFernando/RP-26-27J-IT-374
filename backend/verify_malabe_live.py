"""Explicit local DB-administrator maintenance command; never an HTTP auth bypass.

Creates draft route versions only for the selected Malabe date. No student edits,
geometry calls, geocoding, training or trip actions. Console/report omit pins/keys.
"""
import argparse,json
from datetime import date,datetime,timezone
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from sqlalchemy.orm import Session
from database import get_engine
from models import LandmarkScenario,School
from landmark import SCENARIO,VEHICLE
from route_schemas import GenerateRouteRequest
from route_service import generate_and_store,local_timestamp
from planning_state import execution_guard
from traffic_provider import TrafficSnapshotProvider,baseline_repository
from traffic_google import GoogleRoutesAdapter,ProviderFailure,post_google
from travel_time import Coordinate
from ml.predictor import predictor,TravelTimePredictor


def run(day,am,pm,budget):
    if not 21600<=am<86400 or not 48600<=pm<86400:raise ValueError('AM must be at/after 06:00 and PM at/after 13:30; no call made.')
    run_id='LIVE_VERIFY_'+uuid4().hex;requests=0;results=[]
    predictor.load();baseline_repository.load()
    missing=TravelTimePredictor(artifacts=Path(__file__).parent/'ml'/'artifacts'/'__verification_missing_model__')
    missing.load() # Separate instance; never unload or overwrite the real model.
    def transport(*args):
        nonlocal requests
        if requests>=budget:raise ProviderFailure('verification_total_budget','Explicit whole-verification HTTP budget exhausted.')
        requests+=1
        return post_google(*args)
    with Session(get_engine()) as session:
        sc=session.get(LandmarkScenario,SCENARIO)
        if not sc:raise RuntimeError('Malabe scenario not initialized.')
        for direction in ('morning','afternoon'):
            if execution_guard(session,VEHICLE,direction,day):raise RuntimeError('Active/completed execution guard: no verification changes made.')
        schools=[session.get(School,k) for k in sc.policy['school_ids']]
        if any(not s.location_confirmed or s.latitude is None or s.longitude is None for s in schools):raise RuntimeError('Confirm both school pins first; no live request made.')
        live=GoogleRoutesAdapter(transport=transport)
        stamp=datetime.fromisoformat(local_timestamp(day,am))
        values,errors=live.matrix([Coordinate(s.latitude,s.longitude,s.id) for s in schools],stamp)
        success=all((i,j) in values for i in range(2) for j in range(2) if i!=j) and not errors
        results.append({'phase':'two_school_smoke','success':success,'returned_pairs':len(values),
            'actual_source':'google_live' if success else 'unavailable',
            'departure':stamp.isoformat(),'provider_errors':sorted({e['code'] for e in errors.values()}),'http_requests_so_far':requests})
        def generate(phase,direction,departure,forced=False,model=predictor):
            def factory(request):
                provider=TrafficSnapshotProvider(request,live=GoogleRoutesAdapter(transport=transport),model=model)
                original=provider.precompute
                def precompute(*args):
                    costs=original(*args)
                    costs.metadata.update(verification_run_id=run_id,verification_phase=phase,
                        verification_test=forced,execution_authority='explicit_user_requested_local_maintenance')
                    return costs
                provider.precompute=precompute
                return provider
            request=GenerateRouteRequest(vehicle_id=VEHICLE,direction=direction,service_date=day,departure_seconds=departure,
                provider='google',fallback_policy='ml' if forced else 'none',force_live_failure=forced,
                live_http_budget=0 if forced else 4,include_geometry=False,
                departure_mode='override' if direction=='morning' else 'fixed')
            with patch('route_service.TrafficSnapshotProvider',side_effect=factory):
                result=generate_and_store(session,request,trigger_event_type='administrator_live_verification')
            source=result['provider_source'] or {}
            results.append({'phase':phase,'route_id':result['route_id'],'version':result['version'],'direction':direction,
                'feasibility_status':result['feasibility_status'],'student_count':result['student_count'],
                'requested_provider':source.get('requested_provider'),'actual_source':source.get('duration_source'),
                'planned_departure':result['departure'],'estimate_timestamp':source.get('snapshot_generated_at'),
                'matrix_contains_mixed_sources':source.get('matrix_contains_mixed_sources'),
                'matrix_source_counts':source.get('matrix_source_counts'),'route_source_counts':source.get('route_source_counts'),
                'model_version':source.get('model_version'),'fallback_reasons':source.get('fallback_reasons'),
                'failure_injection_test':forced,'errors':result['errors'],'live_http_requests':source.get('live_http_requests'),
                'http_requests_so_far':requests})
        generate('normal_am','morning',am)
        generate('normal_pm','afternoon',pm)
        try:
            generate('controlled_adapter_failure','morning',am,True)
            generate('controlled_failure_missing_model','morning',am,True,missing)
        finally:
            # Turn test injection off. Cached live estimates are permitted and labelled
            # by source; a fresh call can never exceed the whole-run budget.
            generate('normal_operation_restored','morning',am)
    return {'run_id':run_id,'verified_at':datetime.now(timezone.utc).isoformat(),'service_date':str(day),
        'total_http_request_budget':budget,'actual_http_requests':requests,'results':results,
        'notes':['Local authorized maintenance execution, not a browser login test.',
            'New versions are drafts; publication still requires administrator review.',
            'Departure-time matrix snapshot, not fully time-dependent routing.',
            'No Google estimates exported as measured observations or training labels.']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-live',action='store_true',required=True)
    parser.add_argument('--request-budget',type=int,choices=range(1,10),required=True)
    parser.add_argument('--service-date',type=date.fromisoformat,required=True)
    parser.add_argument('--am-departure',type=int,default=21600)
    parser.add_argument('--pm-departure',type=int,default=48600)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    report=run(args.service_date,args.am_departure,args.pm_departure,args.request_budget)
    args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
