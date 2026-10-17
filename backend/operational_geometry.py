"""Bounded stored-polyline validation and local metric point-to-segment distance.
Metric projection is local equirectangular, suitable for this Sri Lankan prototype,
not an ellipsoidal survey or validated detector accuracy claim.
"""
import math
from arrivals import distance_m
R=6371000.0


def point_polyline_metres(latitude,longitude,points):
    if not points: return None
    def project(p):
        delta=(p[1]-longitude+180)%360-180
        return R*math.radians(delta)*math.cos(math.radians(latitude)),R*math.radians(p[0]-latitude)
    if len(points)==1: return distance_m(latitude,longitude,*points[0])
    best=float('inf')
    for start,end in zip(points,points[1:]):
        ax,ay=project(start);bx,by=project(end);dx,dy=bx-ax,by-ay
        length=dx*dx+dy*dy
        t=max(0,min(1,-(ax*dx+ay*dy)/length)) if length else 0
        best=min(best,math.hypot(ax+t*dx,ay+t*dy))
    return best


def decode_polyline(encoded):
    if not isinstance(encoded,str) or not 1<=len(encoded)<=12000: raise ValueError('Invalid bounded encoded geometry.')
    result=[];index=0;lat=lon=0
    while index<len(encoded):
        delta=[]
        for _ in range(2):
            value=shift=0
            while True:
                if index>=len(encoded) or shift>30: raise ValueError('Truncated/malformed geometry.')
                number=ord(encoded[index])-63;index+=1
                if not 0<=number<=63: raise ValueError('Invalid geometry encoding.')
                value|=(number&31)<<shift;shift+=5
                if number<32: break
            delta.append(~(value>>1) if value&1 else value>>1)
        lat+=delta[0];lon+=delta[1];point=[lat/1e5,lon/1e5]
        if not -90<=point[0]<=90 or not -180<=point[1]<=180: raise ValueError('Invalid geometry coordinates.')
        result.append(point)
        if len(result)>10000: raise ValueError('Geometry point limit exceeded.')
    if len(result)<2: raise ValueError('At least two road geometry points required.')
    return result


def select_geometry(result,stops):
    fallback=[[stop['latitude'],stop['longitude']] for stop in stops]
    road=result.get('road_geometry') or {};reason=road.get('reason','No verified stored provider geometry.')
    if road.get('status')=='available' and road.get('provider')=='google_routes':
        try:
            points=decode_polyline(road.get('encoded_polyline'))
            if not fallback or distance_m(*points[0],*fallback[0])>100 or distance_m(*points[-1],*fallback[-1])>100:
                raise ValueError('Stored provider geometry endpoints do not match this saved route.')
            if any(point_polyline_metres(*stop,points)>100 for stop in fallback): raise ValueError('Stored road geometry misses a saved route stop.')
            return {'quality':'provider_road_geometry','source':'google_routes','approximate':False,'points':points,
                'reason':'Stored provider provenance, encoding and stop coverage checked; not independently verified driven-road accuracy.'}
        except ValueError as error: reason=str(error)
    return {'quality':'approximate_stop_sequence' if len(fallback)>=2 else 'unavailable','source':'stop_sequence' if len(fallback)>=2 else 'unavailable',
        'approximate':True,'points':fallback,'reason':reason+' Stop-sequence deviation is approximate; this is not road geometry.'}
