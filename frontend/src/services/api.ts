export type RouteDirection = 'morning' | 'afternoon';

export interface RouteResponse {
  vehicle_id: string;
  direction: RouteDirection;
  student_count: number;
  capacity: number;
  travel_time_source: string;
  estimated_driving_time_seconds: number;
  estimated_driving_time_minutes: number;
  stops: { sequence: number; location_id: string; name: string }[];
}

function errorDetail(body: unknown): string | undefined {
  if (!body || typeof body !== 'object' || !('detail' in body)) return undefined;
  const detail = body.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      const location = Array.isArray(item.loc) ? item.loc.join('.') : '';
      return `${location ? `${location}: ` : ''}${item.msg || 'Invalid request'}`;
    }).join('; ');
  }
  return undefined;
}

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) { super(message); this.name = 'ApiError'; }
}

export async function apiFetch<T>(path: string, signal?: AbortSignal, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, { ...options, signal });
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    throw new ApiError(errorDetail(body) || `Request failed (${response.status} ${response.statusText})`, response.status);
  }
  return response.json() as Promise<T>;
}

export function fetchRoute(direction: RouteDirection, signal?: AbortSignal) {
  return apiFetch<RouteResponse>(`/routes/${direction}`, signal);
}


export type InputSource = 'simulated' | 'live_provider' | 'measured';
export type LocationMethod = 'manual' | 'google' | 'manual_correction';
export interface LocationFields {
  address: string; latitude: number | null; longitude: number | null;
  location_confirmed: boolean; location_method: LocationMethod;
}
export interface SchoolRecord extends LocationFields {
  id: string; name: string; input_source: InputSource;
  morning_deadline_seconds: number | null; afternoon_finish_seconds: number | null;
}
export interface VehicleRecord {
  id: string; capacity: number; input_source: InputSource;
  start_address: string; start_latitude: number | null; start_longitude: number | null;
  start_confirmed: boolean; start_method: LocationMethod;
  end_address: string; end_latitude: number | null; end_longitude: number | null;
  end_confirmed: boolean; end_method: LocationMethod;
}
export interface StudentRecord {
  id: string;
  name: string;
  home_id: string;
  school_id: string;
  vehicle_id: string;
  input_source: InputSource;
  home_latitude: number | null;
  home_longitude: number | null;
  active: boolean;
  home_address: string;
  location_confirmed: boolean;
  location_method: LocationMethod;
}
export interface StudentWrite {
  home_address: string;
  location_confirmed: true;
  location_method: LocationMethod;
  name: string;
  school_id: string;
  vehicle_id: string;
  home_latitude: number;
  home_longitude: number;
  input_source: InputSource;
}

export const fetchStudents = (signal?: AbortSignal) => apiFetch<StudentRecord[]>('/routing/students', signal);
export const fetchSchools = (signal?: AbortSignal) => apiFetch<SchoolRecord[]>('/routing/schools', signal);
export const fetchVehicles = (signal?: AbortSignal) => apiFetch<VehicleRecord[]>('/routing/vehicles', signal);

export interface RouteComparison {
  before: RouteSummary | null; after: RouteSummary | null;
  delta_after_minus_before: Record<string, number | null>; itinerary_changed: boolean | null;
}
export interface RouteSummary {
  route_id: string; version: number; roster_version: number; feasibility_status: string;
  generated_at: string; solver_runtime_seconds: number | null;
  provider_source?: { provider: string; duration_source: string; training_data_source?: string; model_version?: string } | null;
  distance_metres: number | null; driving_seconds: number | null; service_seconds: number | null;
  waiting_seconds: number | null; total_duration_seconds: number | null;
}
export interface RoutingOutcome {
  event_id: string; trigger_event?: string; generation_status: string; generation_timestamp?: string | null;
  outcome: 'success' | 'failed' | 'deferred' | 'superseded' | 'unchanged'; errors: string[];
  plans: { vehicle_id: string; direction: RouteDirection; roster_version: number; generation_status: string;
    generated: boolean; route_id?: string; route_version?: number; generation_timestamp?: string;
    solver_runtime_seconds?: number | null; errors?: string[]; comparison: Partial<RouteComparison> }[];
}
export interface MutationMetadata { save_status: 'saved'; routing: RoutingOutcome }
export type StudentMutation = StudentRecord & MutationMetadata;
export type SchoolMutation = SchoolRecord & MutationMetadata;
export type VehicleMutation = VehicleRecord & MutationMetadata;

function announceMutation<T extends MutationMetadata>(result: T): T {
  window.dispatchEvent(new CustomEvent<RoutingOutcome>('routing-input-saved', { detail: result.routing }));
  return result;
}
function writeStudent(path: string, method: string, body: unknown, requestKey: string = crypto.randomUUID()) {
  return apiFetch<StudentMutation>(path, undefined, {
    method, headers: { 'Content-Type': 'application/json', 'Idempotency-Key': requestKey }, body: JSON.stringify(body),
  }).then(announceMutation);
}
export const createStudent = (student: StudentWrite, requestKey?: string) => writeStudent('/routing/students', 'POST', student, requestKey);
export const updateStudent = (id: string, student: StudentWrite, requestKey?: string) => writeStudent(`/routing/students/${encodeURIComponent(id)}`, 'PUT', student, requestKey);
export const setStudentActive = (id: string, active: boolean, requestKey?: string) => writeStudent(`/routing/students/${encodeURIComponent(id)}/status`, 'PATCH', { active }, requestKey);
export const transferStudent = (id: string, vehicle_id: string, requestKey?: string) => writeStudent(`/routing/students/${encodeURIComponent(id)}/vehicle`, 'PATCH', { vehicle_id }, requestKey);
export const removeStudent = (id: string, requestKey?: string) => writeStudent(`/routing/students/${encodeURIComponent(id)}`, 'DELETE', {}, requestKey);


export interface MapPoint {
  id: string; location_id: string; name: string;
  kind: 'home' | 'school' | 'vehicle_start' | 'vehicle_end';
  latitude: number; longitude: number; address: string;
  input_source: InputSource; location_method: LocationMethod; location_input_source?: InputSource;
  action?: string; student_id?: string | null; eta?: string; load_after?: number;
}
export interface MapLocations {
  vehicle_id: string; direction: RouteDirection; points: MapPoint[]; missing_locations: string[];
}
export interface GeocodeResult {
  latitude: number; longitude: number; formatted_address: string;
  provider: 'google'; partial_match: boolean; location_confirmed: false;
}
export const fetchMapLocations = (vehicleId: string, direction: RouteDirection, signal?: AbortSignal) =>
  apiFetch<MapLocations>(`/routing/map-locations/${encodeURIComponent(vehicleId)}?direction=${direction}`, signal);
export const geocodeAddress = (address: string, signal?: AbortSignal) => apiFetch<GeocodeResult>('/routing/geocode', signal, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ address }),
});
export function saveSchoolLocation(id: string, location: LocationFields, requestKey: string = crypto.randomUUID()) {
  return apiFetch<SchoolMutation>(`/routing/schools/${encodeURIComponent(id)}/location`, undefined, {
    method: 'PUT', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': requestKey }, body: JSON.stringify(location),
  }).then(announceMutation);
}
export function saveVehicleLocation(id: string, position: 'start' | 'end', location: LocationFields, requestKey: string = crypto.randomUUID()) {
  return apiFetch<VehicleMutation>(`/routing/vehicles/${encodeURIComponent(id)}/locations/${position}`, undefined, {
    method: 'PUT', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': requestKey }, body: JSON.stringify(location),
  }).then(announceMutation);
}


export interface GenerateRouteRequest {
  vehicle_id: string; direction: RouteDirection; service_date: string; departure_seconds: number;
  pickup_service_seconds: number; delivery_service_seconds: number; max_route_seconds: number;
  solver_time_limit_seconds: number; provider: 'simulation' | 'ml' | 'google' | 'baseline' | 'unavailable'; simulation_speed_mps: number | null;
  traffic_scenario?: 'normal' | 'northbound_delay' | 'directed_incident';
  fallback_policy?: 'none' | 'ml' | 'ml_then_baseline'; force_live_failure?: boolean; include_geometry?: boolean;
  weather_flag?: 0 | 1 | null;
}
export interface StoredRouteStop {
  student_name?: string | null; school_name?: string | null;
  travel_source?: { source: string; fallback_reason?: string | null; unavailable_reason?: string | null; distance_source?: string; scenario_modified?: boolean };
  sequence: number; event_id: string; location_id: string; name: string;
  action: 'start' | 'pickup' | 'delivery' | 'end'; student_id: string | null; school_id: string | null;
  latitude: number; longitude: number; address: string; input_source: InputSource; location_method: LocationMethod;
  arrival_seconds: number; eta_seconds: number; departure_seconds: number;
  arrival: string; eta: string; departure: string;
  driving_seconds_from_previous: number; distance_metres_from_previous: number;
  service_seconds: number; waiting_seconds: number; load_before: number; load_after: number;
}
export interface StoredRoute {
  route_id: string; version: number; vehicle_id: string; direction: RouteDirection; service_date: string;
  departure: string; departure_seconds: number; timezone: string; generated_at: string;
  student_count: number; capacity: number; feasibility_status: string; errors: string[];
  stops: StoredRouteStop[]; distance_metres: number | null; driving_seconds: number | null;
  service_seconds: number | null; waiting_seconds: number | null; total_duration_seconds: number | null;
  solver_runtime_seconds: number | null; solver_status: string; optimality: string; assignment_policy: string;
  provider_source: { provider: string; duration_source: string; distance_source: string; distance_is_approximate: boolean; speed_metres_per_second?: number; costs_computed?: boolean; model_version?: string; training_data_source?: string; warnings?: string[]; time_assumption?: string;
    requested_provider?: string; route_is_mixed?: boolean; route_source_counts?: Record<string, number>; route_fallback_reasons?: string[];
    fallback_reasons?: string[]; live_configured?: boolean; matrix_snapshot_id?: string; traffic_scenario?: string; scenario_modified_directed_arcs?: number } | null;
  alternative_comparison?: { matrix_snapshot_id: string; same_matrix: boolean; reference_label: string; reference_feasibility_status: string;
    reference_errors: string[]; reference: Record<string, number> | null; selected: Record<string, number>; reference_minus_selected: Record<string, number | null>; sequence_changed: boolean; note: string } | null;
  road_geometry?: { status: string; reason?: string; map_available?: boolean; map_reason?: string; description?: string } | null;
  request_settings: GenerateRouteRequest;
  roster_version: number; current_roster_version: number; is_current: boolean;
  planning_status: string; planning_errors: string[]; trigger_event_id: string | null; trigger_event: string;
  execution_status: 'pre_trip' | 'active' | 'completed' | 'cancelled'; comparison: Partial<RouteComparison>;
}
export const fetchLatestRoute = (vehicleId: string, direction: RouteDirection, signal?: AbortSignal) =>
  apiFetch<StoredRoute>(`/routes/latest?vehicle_id=${encodeURIComponent(vehicleId)}&direction=${direction}`, signal);
export const generateStoredRoute = (request: GenerateRouteRequest) => apiFetch<StoredRoute>('/routes/generate', undefined, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request),
});
export const saveSchoolSchedule = (schoolId: string, morning_deadline_seconds: number, afternoon_finish_seconds: number, requestKey: string = crypto.randomUUID()) =>
  apiFetch<SchoolMutation>(`/routing/schools/${encodeURIComponent(schoolId)}/schedule`, undefined, {
    method: 'PUT', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': requestKey }, body: JSON.stringify({ morning_deadline_seconds, afternoon_finish_seconds }),
  }).then(announceMutation);


export interface PlanStatus {
  vehicle_id: string; direction: RouteDirection; roster_version: number; generation_status: string;
  student_count: number; capacity: number;
  errors: string[]; is_current: boolean; route_id: string | null; trigger_event_id: string | null;
  generation_timestamp: string | null; solver_runtime_seconds: number | null; comparison: Partial<RouteComparison>;
}
export const fetchPlanStatus = (vehicleId: string, direction: RouteDirection, signal?: AbortSignal) =>
  apiFetch<PlanStatus>(`/routing/plans/${encodeURIComponent(vehicleId)}/${direction}`, signal);
export const retryRoutingEvent = (eventId: string) => apiFetch<RoutingOutcome>(`/routing/events/${encodeURIComponent(eventId)}/retry`, undefined, { method: 'POST' }).then((outcome) => { window.dispatchEvent(new CustomEvent('routing-input-saved', { detail: outcome })); return outcome; });

export interface MLStatus { available: boolean; status: string; reason: string | null; model_version: string | null; disclaimer: string }
export const fetchMLStatus = (signal?: AbortSignal) => apiFetch<MLStatus>('/ml/status', signal);
export interface TrafficStatus {
  google: { configured: boolean; status: string; reason: string | null; timeout_seconds: number; cache_ttl_seconds: number; road_geometry_supported: boolean; google_map_display_configured: boolean };
  baseline: { available: boolean; reason: string | null }; time_assumption: string;
}
export const fetchTrafficStatus = (signal?: AbortSignal) => apiFetch<TrafficStatus>('/traffic/status', signal);


export interface TripRecord {
  trip_id: string; route_id: string; route_version: number; vehicle_id: string; direction: RouteDirection;
  state: 'PLANNED' | 'ACTIVE' | 'COMPLETED' | 'CANCELLED';
  created_at: string; started_at: string | null; completed_at: string | null; cancelled_at: string | null;
  cancellation_reason: string | null; action_source: 'manual_prototype';
  unfinished_action_count: number; passenger_event_recording: string;
  unfinished_actions: { event_id: string; sequence: number; action: string; student_id: string; student_name: string | null; school_name: string | null; name: string; status: 'PENDING' | 'MISSED' | 'CANCELLED' }[];
  route: StoredRoute;
}
export const fetchCurrentTrip = (vehicleId: string, direction: RouteDirection, signal?: AbortSignal) =>
  apiFetch<{ trip: TripRecord | null }>(`/trips/current?vehicle_id=${encodeURIComponent(vehicleId)}&direction=${direction}`, signal);
export const createPlannedTrip = (routeId: string, pickup_mode: 'production' | 'simulation_demo' = 'production', pickup_scope?: 'per_stop' | 'per_school') => apiFetch<TripRecord>('/trips', undefined, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ route_id: routeId, pickup_mode, pickup_scope }),
});
export const changeTripState = (tripId: string, action: 'start' | 'complete' | 'cancel', reason?: string) =>
  apiFetch<TripRecord>(`/trips/${encodeURIComponent(tripId)}/${action}`, undefined, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, ...(action === 'cancel' ? { body: JSON.stringify({ reason }) } : {}),
  });


export interface VehiclePosition {
  id: string; sample_id: string; vehicle_id: string; trip_id: string | null;
  source: 'simulation' | 'actual_device'; latitude: number; longitude: number;
  speed_mps: number | null; recorded_at: string; received_at: string;
}
export interface LatestPosition {
  position: VehiclePosition | null; age_seconds: number | null; status: 'fresh' | 'stale' | 'unknown';
  stale_after_seconds: number; movement_state: 'unknown'; note: string;
}
export const fetchVehiclePosition = (vehicleId: string, signal?: AbortSignal) =>
  apiFetch<LatestPosition>(`/routing/vehicles/${encodeURIComponent(vehicleId)}/positions/latest`, signal);


export interface TripArrival {
  trip_id: string; route_id: string; state: 'approaching' | 'arrival_candidate' | 'arrived' | 'gps_unknown';
  reason: string | null; current_stop: StoredRouteStop | null; position_age_seconds: number | null;
  gps_status: string; distance_metres: number | null; observation_count: number; candidate_started_at: string | null;
  settings: { radius_metres: number; exit_radius_metres: number; dwell_seconds: number; min_observations: number; max_gap_seconds: number; freshness_seconds: number };
  arrival_event: { event_id: string; arrived_at: string; candidate_started_at: string; source: string; route_id: string; stop_sequence: number } | null;
  can_advance: boolean; note: string;
}
export const fetchTripArrival = (tripId: string, signal?: AbortSignal) => apiFetch<TripArrival>(`/trips/${encodeURIComponent(tripId)}/arrival`, signal);
export const advanceTripStop = (tripId: string, sequence: number) => apiFetch<TripArrival>(`/trips/${encodeURIComponent(tripId)}/advance-stop?expected_stop_sequence=${sequence}`, undefined, { method: 'POST' });


export type PickupState = 'SCHEDULED' | 'ARRIVED' | 'WAITING' | 'PICKED_UP' | 'MISSED' | 'CANCELLED';
export interface PickupPolicy { supervisor_confirmed: boolean; policy: string; morning_scope: 'per_stop'; afternoon_scope: 'per_stop' | 'per_school'; production_duration_seconds: number; demo_duration_seconds: number; deadline_rule: string }
export interface PickupWindows {
  trip_id: string; server_now: string; settings: { mode: 'production' | 'simulation_demo'; scope: string; duration_seconds: number; policy: string } | null;
  windows: { window_id: string; scope: string; scope_key: string; school_id: string | null; state: PickupState;
    mode: 'production' | 'simulation_demo'; duration_seconds: number; started_at: string | null; deadline_at: string | null;
    remaining_seconds: number | null; expiry_pending: boolean;
    outcomes: { student_id: string; student_name: string; stop_sequence: number; state: PickupState;
      changed_at: string; picked_up_at: string | null; action_source: string; can_confirm: boolean; can_cancel: boolean }[] }[];
}
export const fetchPickupPolicy = (signal?: AbortSignal) => apiFetch<PickupPolicy>('/pickup-policy', signal);
export const fetchPickupWindows = (tripId: string, signal?: AbortSignal) => apiFetch<PickupWindows>(`/trips/${encodeURIComponent(tripId)}/pickup-windows`, signal);
export const confirmPickup = (tripId: string, studentId: string) => apiFetch<PickupWindows>(`/trips/${encodeURIComponent(tripId)}/pickups/${encodeURIComponent(studentId)}/confirm`, undefined, { method: 'POST' });
export const cancelPickup = (tripId: string, studentId: string, reason: string) => apiFetch<PickupWindows>(`/trips/${encodeURIComponent(tripId)}/pickups/${encodeURIComponent(studentId)}/cancel`, undefined, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ reason }) });


export type NotificationRecipient = 'admin' | 'parent';
export interface MissedPickupNotice {
  id: string; order_id: number; kind: 'missed_pickup'; trip_id: string; window_id: string;
  student_id: string; student_name: string; vehicle_id: string; route_id: string; stop_sequence: number;
  occurred_at: string; created_at: string; action_source: string; position_source: string | null;
  mode: 'production' | 'simulation_demo'; delivery_status: 'in_app_event_created'; message: string;
  read: boolean; read_at: string | null;
}
export interface PersistentInbox { recipient: NotificationRecipient; student_id: string | null; notifications: MissedPickupNotice[]; unread_count: number; truncated: boolean; next_before_order_id: number | null }
export const fetchPersistentInbox = (recipient: NotificationRecipient, studentId: string, signal?: AbortSignal, before?: number) =>
  apiFetch<PersistentInbox>(`/routing/notifications?recipient=${recipient}${recipient==='parent'?`&student_id=${encodeURIComponent(studentId)}`:''}&limit=50${before?`&before_order_id=${before}`:''}`,signal);
export const setNoticeRead = (id: string, recipient: NotificationRecipient, studentId: string, read: boolean) =>
  apiFetch<MissedPickupNotice>(`/routing/notifications/${encodeURIComponent(id)}/read`,undefined,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({recipient,...(recipient==='parent'?{student_id:studentId}:{}),read})});


export interface OperationalEvents {
  trip_id: string; route_id: string; gps_state: 'fresh' | 'unknown'; position_age_seconds: number | null; source: string | null;
  settings: { selected_deviation_metres: number; deviation_recovery_metres: number; deviation_seconds: number; recovery_seconds: number;
    stop_seconds: number; low_movement_mps: number; stop_radius_metres: number; stop_recovery_metres: number; expected_dwell_radius_metres: number;
    min_observations: number; max_gap_seconds: number; freshness_seconds: number } | null;
  geometry: { quality: string; source: string; approximate: boolean; reason: string } | null;
  distance_metres: number | null; derived_step_speed_mps: number | null; expected_waiting: string | null;
  deviation_candidate: boolean; stop_candidate: boolean; truncated: boolean; note: string;
  episodes: { id: string; kind: 'route_deviation' | 'unexpected_stop'; episode: number; status: 'ACTIVE' | 'RECOVERED' | 'CLOSED';
    started_at: string; confirmed_at: string; recovered_at: string | null; closed_at: string | null;
    recovery_reason: string | null; source: string; recovery_source: string | null; geometry_quality: string; geometry_source: string }[];
}
export const fetchOperationalEvents = (tripId: string, signal?: AbortSignal) => apiFetch<OperationalEvents>(`/trips/${encodeURIComponent(tripId)}/operational-events`,signal);
