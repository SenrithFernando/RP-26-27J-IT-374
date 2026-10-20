import type { MapPoint, StoredRoute } from './api';

/** The same stored action-to-map adapter is used by Admin and Driver. */
export function routePoints(route: StoredRoute): MapPoint[] {
  return route.stops.map((stop) => ({ id: `${route.route_id}:${stop.sequence}`, location_id: stop.event_id,
    name: stop.name, kind: stop.action === 'start' ? 'vehicle_start' : stop.action === 'end' ? 'vehicle_end' :
      route.research_journey ? 'landmark' : (route.direction === 'morning' ? stop.action === 'pickup' : stop.action === 'delivery') ? 'home' : 'school',
    latitude: stop.latitude, longitude: stop.longitude, address: stop.address, input_source: stop.input_source,
    location_method: stop.location_method, action: stop.action, student_id: stop.student_id, eta: stop.eta ?? undefined, load_after: stop.load_after }));
}

export function localPlanningDate() {
  const parts = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Colombo', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
  const part = (type: string) => parts.find((value) => value.type === type)?.value;
  return `${part('year')}-${part('month')}-${part('day')}`;
}
