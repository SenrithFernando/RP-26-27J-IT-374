"""Create explicit simulation scenarios for one selected active saved trip.
Use existing replay_positions.py --speed 1 --rebase-to-now; faster playback may
not satisfy sustained GPS-time thresholds. No paid provider calls are made.
"""
import argparse,csv,json,math
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.request import urlopen
from operational_geometry import select_geometry,point_polyline_metres
from arrivals import distance_m


def generate(trip,settings,out_dir):
    stops=trip['route']['stops'];geometry=select_geometry(trip['route'],stops);line=geometry['points']
    if len(line)<2:raise ValueError('Saved trip needs usable geometry.')
    radius=settings['expected_dwell_radius_metres'];candidates=[]
    for a,b in zip(line,line[1:]):
        for fraction in (.25,.5,.75):
            point=[a[0]+(b[0]-a[0])*fraction,a[1]+(b[1]-a[1])*fraction]
            clearance=min(distance_m(*point,s['latitude'],s['longitude']) for s in stops)
            candidates.append((clearance,point,a,b,fraction))
    clearance,mid,a,b,centre=max(candidates,key=lambda x:x[0])
    if clearance<=radius+5:raise ValueError('No point clear of expected-stop geofences. Select a synthetic trip with a longer inter-stop corridor; do not invent an unexpected stop at a school/depot.')
    north=max(settings['selected_deviation_metres']*3,1000)/111194.9266
    outside=None
    for lat,lon in ((mid[0]+north,mid[1]),(mid[0]-north,mid[1]),(mid[0],mid[1]+north)):
        if -90<=lat<=90 and -180<=lon<=180 and point_polyline_metres(lat,lon,line)>settings['selected_deviation_metres']:
            outside=[lat,lon];break
    if outside is None:raise ValueError('Could not construct a clearly off-route simulation point.')
    step=min(2,settings['max_gap_seconds']/2)
    def stationary(point,duration):return [(i*step,point) for i in range(math.ceil(duration/step)+1)]
    def travel(duration):
        # Samples move along the chosen saved segment, not an invented road.
        count=max(3,math.ceil(duration/step))
        length=distance_m(*a,*b)
        half=min(centre,1-centre,.45,duration*5/(2*length))
        return [(i*step,[a[0]+(b[0]-a[0])*(centre-half+2*half*i/count),a[1]+(b[1]-a[1])*(centre-half+2*half*i/count)]) for i in range(count+1)]
    dev=stationary(outside,settings['deviation_seconds']+step*2)
    return_to=stationary(mid,settings['recovery_seconds']+step*2)
    recovery=dev+[(dev[-1][0]+step+t,p) for t,p in return_to]
    waiting=[trip['route']['stops'][1]['latitude'],trip['route']['stops'][1]['longitude']]
    # A gap is represented by NO rows, never by zero-speed fabricated positions.
    normal=travel(max(12,settings['recovery_seconds']+step*2))
    gap=normal+[(normal[-1][0]+settings['freshness_seconds']+settings['max_gap_seconds']+step+t,p) for t,p in normal]
    scenarios={'normal_travel':normal,'sustained_deviation':dev,'recovery':recovery,
        'expected_waiting':stationary(waiting,settings['stop_seconds']+step*2),
        'unexpected_stop':stationary(mid,settings['stop_seconds']+step*2),'gps_loss':gap}
    out_dir.mkdir(parents=True,exist_ok=True);start=datetime.now(timezone.utc)
    for name,rows in scenarios.items():
        with (out_dir/(name+'.csv')).open('w',newline='',encoding='utf-8') as handle:
            writer=csv.DictWriter(handle,fieldnames=['recorded_at','latitude','longitude','speed_mps','source','description']);writer.writeheader()
            for second,point in rows:
                writer.writerow({'recorded_at':(start+timedelta(seconds=second)).isoformat(),'latitude':point[0],'longitude':point[1],
                    'speed_mps':'','source':'simulation','description':f'Synthetic {name}; {geometry["quality"]}; not a driven road trace'})
    manifest={'vehicle_id':trip['vehicle_id'],'trip_id':trip['trip_id'],'route_id':trip['route_id'],'geometry_quality':geometry['quality'],
        'geometry_source':geometry['source'],'settings':settings,'scenarios':{name:len(rows) for name,rows in scenarios.items()},
        'note':'Every row is simulation. Movement/stop scenarios are operational demonstrations, not validated accuracy or crash diagnoses. Sustained deviation may also trigger a low-movement event if stationary long enough; both are independent operational episodes.'}
    (out_dir/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--vehicle-id',required=True);parser.add_argument('--trip-id',required=True)
    parser.add_argument('--base-url',default='http://127.0.0.1:8000');parser.add_argument('--out-dir',type=Path,default=Path('../data/operational_replays'))
    args=parser.parse_args()
    def get(path):
        with urlopen(args.base_url.rstrip('/')+path,timeout=10) as response:return json.load(response)
    trip=get('/trips/'+args.trip_id)
    if trip['vehicle_id']!=args.vehicle_id or trip['state']!='ACTIVE':parser.error('Select the correct ACTIVE trip and vehicle explicitly.')
    view=get('/trips/'+args.trip_id+'/operational-events')
    if not view['settings']:parser.error('Monitor settings unavailable; start a fresh trip or ingest a fresh sample on an existing active trip.')
    print(json.dumps(generate(trip,view['settings'],args.out_dir),indent=2))


if __name__=='__main__':main()
