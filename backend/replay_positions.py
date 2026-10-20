"""Terminal-controlled simulation only; never a measured driven road trace."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen
from uuid import uuid4
import cli_auth


def request(base, path, body=None):
    req=Request(base.rstrip('/')+path,data=json.dumps(body).encode() if body is not None else None,
                headers={'Content-Type':'application/json',**cli_auth.headers()},method='POST' if body is not None else 'GET')
    with urlopen(req,timeout=10) as response: return json.load(response)


def stamp(value):
    value=datetime.fromisoformat(value.replace('Z','+00:00'))
    if value.tzinfo is None: raise ValueError('Fixture timestamps must include a timezone.')
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:8000')
    parser.add_argument('--username',help='Username only; password entered at a hidden prompt.')
    parser.add_argument('--vehicle-id',required=True)
    parser.add_argument('--trip-id',required=True)
    parser.add_argument('--fixture',type=Path,required=True)
    parser.add_argument('--make-fixture',action='store_true',help='Create synthetic interpolation of the selected trip stop sequence, then exit.')
    parser.add_argument('--speed',type=float,default=1,help='Replay rate: 10 means ten fixture seconds per wall-clock second.')
    parser.add_argument('--rebase-to-now',action='store_true',help='Use a current compressed simulation timeline; otherwise preserve fixture timestamps.')
    args=parser.parse_args()
    cli_auth.configure(args.base_url,args.username)
    import math
    if not math.isfinite(args.speed) or args.speed<=0: parser.error('--speed must be finite and positive.')
    trip=request(args.base_url,'/trips/'+args.trip_id)
    if trip['vehicle_id']!=args.vehicle_id: parser.error('Trip does not belong to the explicitly selected vehicle.')
    if args.make_fixture:
        stops=trip['route']['stops']
        if len(stops)<2: parser.error('Trip has no usable stop sequence.')
        args.fixture.parent.mkdir(parents=True,exist_ok=True)
        start=stamp(trip['route']['departure'])
        with args.fixture.open('w',newline='',encoding='utf-8') as handle:
            writer=csv.DictWriter(handle,fieldnames=['recorded_at','latitude','longitude','speed_mps','source','description'])
            writer.writeheader()
            for index,(a,b) in enumerate(zip(stops,stops[1:])):
                for step in range(10):
                    fraction=step/10
                    writer.writerow(dict(recorded_at=(start+timedelta(seconds=(index*10+step)*2)).isoformat(),
                        latitude=a['latitude']+(b['latitude']-a['latitude'])*fraction,
                        longitude=a['longitude']+(b['longitude']-a['longitude'])*fraction,
                        speed_mps='',source='simulation',description='Synthetic stop-sequence movement; not a driven road trace'))
            writer.writerow(dict(recorded_at=(start+timedelta(seconds=(len(stops)-1)*20)).isoformat(),latitude=stops[-1]['latitude'],
                longitude=stops[-1]['longitude'],speed_mps='',source='simulation',description='Synthetic stop-sequence movement; not a driven road trace'))
        print(f'Wrote {args.fixture}: synthetic stop-sequence fixture, not a driven road trace. Speed unknown, not invented.')
        return
    with args.fixture.open(encoding='utf-8-sig',newline='') as handle: rows=list(csv.DictReader(handle))
    if not rows or len(rows)>10000: parser.error('Fixture must contain 1 to 10000 samples.')
    from positions import PositionInput
    times=[stamp(row['recorded_at']) for row in rows]
    if any(b<a for a,b in zip(times,times[1:])): parser.error('Replay fixture timestamps must be ordered.')
    # Validate every row before ingesting any. Source is always simulation, regardless of CSV source.
    for row,recorded in zip(rows,times):
        PositionInput(sample_id='validation',trip_id=args.trip_id,source='simulation',recorded_at=recorded,
            latitude=float(row['latitude']),longitude=float(row['longitude']),speed_mps=float(row['speed_mps']) if row.get('speed_mps') else None,
            accuracy_m=float(row['accuracy_m']) if row.get('accuracy_m') else None)
    print(f'SIMULATION ONLY / {args.vehicle_id} / {args.trip_id} / {len(rows)} samples. Synthetic movement, not a driven road trace.')
    input('Press Enter to start; Ctrl+C stops without ending or changing the trip. ')
    start=datetime.now(timezone.utc); clock=time.monotonic(); run=uuid4().hex
    try:
        for index,(row,recorded) in enumerate(zip(rows,times)):
            offset=(recorded-times[0]).total_seconds()/args.speed
            remaining=clock+offset-time.monotonic()
            if remaining>0: time.sleep(remaining)
            sample={'sample_id':f'replay-{run}-{index}','trip_id':args.trip_id,'source':'simulation',
                'recorded_at':(start+timedelta(seconds=offset)).isoformat() if args.rebase_to_now else recorded.isoformat(),
                'latitude':float(row['latitude']),'longitude':float(row['longitude']),
                'speed_mps':float(row['speed_mps']) if row.get('speed_mps') else None,
                'accuracy_m':float(row['accuracy_m']) if row.get('accuracy_m') else None}
            response=request(args.base_url,f'/routing/vehicles/{args.vehicle_id}/positions',sample)
            print(f'{index+1}/{len(rows)} simulation / duplicate={response["duplicate"]} / advances_latest={response["advances_latest"]}')
    except KeyboardInterrupt:
        print('Replay stopped. Persisted samples remain; trip lifecycle unchanged.')


if __name__=='__main__':
    try: main()
    except KeyboardInterrupt: print('Replay cancelled before ingestion; trip lifecycle unchanged.')
