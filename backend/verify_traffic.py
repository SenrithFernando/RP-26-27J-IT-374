"""Local Stage 7 demonstration. Stores real attempts; never requires a live key."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--vehicle-id', default='S4_VAN_A')
    args = parser.parse_args()
    def request(path, body=None):
        req = Request(args.base_url+path, data=None if body is None else json.dumps(body).encode(), headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=90) as response: return json.load(response)
    status = request('/traffic/status')
    if not status['ml']['available']: raise RuntimeError('Cannot prove XGBoost fallback: '+str(status['ml']['reason']))
    date = (datetime.now(ZoneInfo('Asia/Colombo')).date()+timedelta(days=1)).isoformat()
    common = dict(vehicle_id=args.vehicle_id, direction='morning', service_date=date,
        departure_seconds=21600, pickup_service_seconds=30, delivery_service_seconds=30, solver_time_limit_seconds=2)
    attempts = {}
    for label, settings in [('normal',dict(provider='simulation')), ('corridor_delay',dict(provider='simulation',traffic_scenario='northbound_delay')),
            ('explicit_baseline',dict(provider='baseline')), ('explicit_unavailable',dict(provider='unavailable'))]:
        attempts[label] = request('/routes/generate',{**common,**settings})
    assert attempts['explicit_unavailable']['feasibility_status'] == 'unavailable'
    assert attempts['explicit_unavailable']['driving_seconds'] is None and not attempts['explicit_unavailable']['stops']
    heavy = attempts['corridor_delay']
    if heavy['feasibility_status'] == 'feasible':
        comparison = heavy['alternative_comparison']
        assert comparison['same_matrix'] and comparison['matrix_snapshot_id'] == heavy['provider_source']['matrix_snapshot_id']
    if not status['google']['configured']:
        attempts['missing_live_credentials'] = request('/routes/generate',{**common,'provider':'google','fallback_policy':'ml'})
    for direction, departure in [('morning',21600),('afternoon',45000)]:
        result = request('/routes/generate',{**common,'direction':direction,'departure_seconds':departure,
            'provider':'google','force_live_failure':True,'fallback_policy':'ml'})
        assert result['feasibility_status'] == 'feasible', result['errors']
        assert result['provider_source']['duration_source'] == 'ml_prediction'
        assert result['provider_source']['model_version'] == status['ml']['model_version']
        assert all(s['travel_source']['source'] in ('start','geographic_zero','ml_prediction') for s in result['stops'])
        assert any(s['travel_source'].get('failure_code') == 'forced_live_failure' for s in result['stops'])
        latest = request(f'/routes/latest?vehicle_id={args.vehicle_id}&direction={direction}')
        assert latest['route_id'] == result['route_id'] and latest['version'] == result['version']
        attempts['forced_live_failure_'+direction] = result
    output = Path(__file__).resolve().parents[1] / 'docs' / 'stage7_traffic_demo.json'
    output.write_text(json.dumps({'recorded_at':datetime.now(timezone.utc).isoformat(),'status':status,'attempts':attempts,
        'note':'Executed simulation, baseline and loaded-XGBoost fallback results. No successful live Google observation is claimed. Mocked mixed-source contracts are covered separately by unit tests.'},indent=2,allow_nan=False),encoding='utf-8')
    summary = {label:{'route_id':r['route_id'],'version':r['version'],'status':r['feasibility_status'],
        'source':r['provider_source']['duration_source'],'source_counts':r['provider_source'].get('route_source_counts'),
        'driving_seconds':r['driving_seconds'],'total_seconds':r['total_duration_seconds'],
        'fallback_reasons':r['provider_source'].get('fallback_reasons'), 'matrix':r['provider_source'].get('matrix_snapshot_id'),
        'scenario_modified_arcs':r['provider_source'].get('scenario_modified_directed_arcs'),
        'same_snapshot_comparison':r.get('alternative_comparison')} for label,r in attempts.items()}
    print(json.dumps({'google_configured':status['google']['configured'],'model':status['ml']['model_version'],'attempts':summary,'output':str(output)},indent=2))


if __name__ == '__main__': main()
