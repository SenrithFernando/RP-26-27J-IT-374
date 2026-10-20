"""Projection of provisional registration locations; address match is not a stop review."""
from datetime import datetime,timezone
from fastapi import HTTPException
from geocoding import GeocodeRequest,geocode


def counts(rows):
    return {key:sum(bool(r.get('attempted')) if key=='attempted' else r['status']==key for r in rows)
            for key in ('attempted','successful','ambiguous','failed','pending_budget','unchanged','supplied_pin')}


def project(record,target,prefixes,budget,external_id):
    changed=False;address_changed=False
    supplied_pin=record.latitude is not None
    for prefix in prefixes:
        if record.address is not None and getattr(target,prefix+'address')!=record.address:
            address_changed=True
        for key in ('address','latitude','longitude'):
            value=getattr(record,key)
            if value is not None and getattr(target,prefix+key)!=value:
                setattr(target,prefix+key,value);changed=True
    lookup_missing=record.address is not None and not supplied_pin and budget>0 and any(getattr(target,p+'latitude') is None or getattr(target,p+'longitude') is None for p in prefixes)
    if not changed and not lookup_missing:return False,None
    # Never retain old reviewed coordinates after an address-only change.
    if address_changed and not supplied_pin:
        for prefix in prefixes:
            setattr(target,prefix+'latitude',None);setattr(target,prefix+'longitude',None)
    outcome={'external_id':external_id,'supplied_address':record.address,'attempted':False,
        'status':'supplied_pin' if supplied_pin else 'pending_budget','provider_result':None,
        'input_provenance':'landmark_test','result_source':'user_supplied' if supplied_pin else 'unavailable',
        'review_status':'vehicle_stop_review_required','recorded_at':datetime.now(timezone.utc).isoformat(),
        'note':'Address/building matches do not establish accessible vehicle stopping points. Manual review required.'}
    if (address_changed or lookup_missing) and record.address is not None and budget>0:
        outcome['attempted']=True
        try:
            result=geocode(GeocodeRequest(address=record.address))
            outcome.update(status='ambiguous' if result.get('ambiguous') or result.get('partial_match') else 'successful',provider_result=result,result_source='live_provider')
            if not supplied_pin:
                for prefix in prefixes:
                    setattr(target,prefix+'latitude',result['latitude']);setattr(target,prefix+'longitude',result['longitude'])
        except HTTPException as error:
            # Provider errors are already sanitized; never persist raw exceptions/URLs.
            outcome.update(status='failed',error_status=error.status_code,error='Configured geocoding unavailable, rejected, or no match. Review/correct the pin manually.')
        except Exception:
            outcome.update(status='failed',error='Unexpected geocoding failure; no coordinates invented. Review manually.')
    elif address_changed:
        outcome['note']='No geocoding request authorized in this event budget. Address saved; manual vehicle-stop review required.'
    for prefix in prefixes:
        confirm={'home_':'location_confirmed','':'location_confirmed','start_':'start_confirmed','end_':'end_confirmed'}[prefix]
        method={'home_':'location_method','':'location_method','start_':'start_method','end_':'end_method'}[prefix]
        setattr(target,confirm,False)
        setattr(target,method,'google' if outcome['provider_result'] and not supplied_pin else 'manual')
    return True,outcome
