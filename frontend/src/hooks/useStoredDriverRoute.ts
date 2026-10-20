import { useEffect, useRef, useState } from 'react';
import { ApiError, apiFetch, fetchLatestRoute, fetchPlanStatus, fetchCurrentTrip, TripRecord, PlanStatus, RouteDirection, StoredRoute } from '../services/api';

export const DRIVER_ROUTE_POLL_MS = 15_000;
const REQUEST_TIMEOUT_MS = 12_000;
type View = { publicationStatus?:string; trip: TripRecord | null; tripError: string | null; key: string; route: StoredRoute | null; plan: PlanStatus | null; error: string | null;
  noRoute: boolean; refreshing: boolean; checkedAt: string | null };
const empty = (key: string): View => ({ trip: null, tripError: null, key, route: null, plan: null, error: null, noRoute: false, refreshing: false, checkedAt: null });
const message = (error: unknown) => error instanceof Error ? error.message : 'Stored route request failed.';

/** Read-only polling, serialized per selection; no generation or mutation imports. */
export function useStoredDriverRoute(vehicleId: string, direction: RouteDirection, serviceDate?: string, purpose: 'school' | 'research' = 'school') {
  const key = `${vehicleId}:${direction}:${serviceDate}:${purpose}`;
  const [view, setView] = useState<View>(() => empty(key));
  const [visible, setVisible] = useState(document.visibilityState === 'visible');
  const refresh = useRef<(() => void) | null>(null);

  useEffect(() => {
    let alive = true, sequence = 0;
    let controller: AbortController | null = null;
    let poll: ReturnType<typeof setTimeout> | undefined;
    let deadline: ReturnType<typeof setTimeout> | undefined;
    const cancel = () => { ++sequence; controller?.abort(); clearTimeout(poll); clearTimeout(deadline); };
    const load = () => {
      if (!alive || !vehicleId || document.visibilityState !== 'visible') return;
      cancel();
      const id = sequence;
      controller = new AbortController();
      let timedOut = false;
      const currentController = controller;
      const currentDeadline = setTimeout(() => { timedOut = true; currentController.abort(); }, REQUEST_TIMEOUT_MS);
      deadline = currentDeadline;
      setView((prev) => ({ ...(prev.key === key ? prev : empty(key)), refreshing: true }));
      type Result={published_route:StoredRoute|null;publication_status:string;trip:TripRecord|null;planOverride?:PlanStatus|null;error?:string|null;tripError?:string|null};
      const request:Promise<Result>=serviceDate?apiFetch<Result>(`${purpose==='research'?'/research-routes/current':'/routes/published'}?vehicle_id=${encodeURIComponent(vehicleId)}&direction=${direction}&service_date=${serviceDate}`,controller.signal):Promise.allSettled([fetchLatestRoute(vehicleId,direction,controller.signal),fetchPlanStatus(vehicleId,direction,controller.signal),fetchCurrentTrip(vehicleId,direction,controller.signal)]).then(([route,plan,trip])=>{
        const absent=route.status==='rejected'&&route.reason instanceof ApiError&&route.reason.status===404;
        return {published_route:route.status==='fulfilled'?route.value:null,publication_status:'admin_latest_plan',trip:trip.status==='fulfilled'?trip.value.trip:null,planOverride:plan.status==='fulfilled'?plan.value:null,
          error:[route.status==='rejected'&&!absent?message(route.reason):null,plan.status==='rejected'?`Plan freshness could not be verified: ${message(plan.reason)}`:null].filter(Boolean).join(' ')||null,tripError:trip.status==='rejected'?message(trip.reason):null};
      });
      request.then(result => {
          clearTimeout(currentDeadline);
          if (!alive || id !== sequence) return;
          const route=result.published_route;
          const plan:PlanStatus|null=result.planOverride??(route?{vehicle_id:route.vehicle_id,direction:route.direction,roster_version:route.roster_version,generation_status:route.planning_status,student_count:route.student_count,capacity:route.capacity,errors:route.planning_errors,is_current:route.is_current,route_id:route.route_id,trigger_event_id:route.trigger_event_id,generation_timestamp:route.generated_at,solver_runtime_seconds:route.solver_runtime_seconds,comparison:route.comparison}:null);
          setView({key,route,plan,trip:result.trip,tripError:result.tripError??null,publicationStatus:result.publication_status,noRoute:!route,refreshing:false,error:result.error??null,checkedAt:new Date().toISOString()});
          if (document.visibilityState === 'visible') poll = setTimeout(load, DRIVER_ROUTE_POLL_MS);
        }).catch(error=>{
          clearTimeout(currentDeadline);
          if(!alive||id!==sequence)return;
          setView({...empty(key),error:timedOut?'Stored route request timed out.':message(error),checkedAt:new Date().toISOString()});
          if(document.visibilityState==='visible')poll=setTimeout(load,DRIVER_ROUTE_POLL_MS);
        });
    };
    const visibility = () => {
      const isVisible = document.visibilityState === 'visible'; setVisible(isVisible);
      if (isVisible) load();
      else { cancel(); setView((prev) => ({ ...prev, refreshing: false })); }
    };
    setView(empty(key));
    refresh.current = load;
    document.addEventListener('visibilitychange', visibility);
    load();
    return () => {
      alive = false; cancel(); refresh.current = null;
      document.removeEventListener('visibilitychange', visibility);
    };
  }, [vehicleId, direction, serviceDate, purpose, key]);

  return { view: view.key === key ? view : empty(key), visible, refresh: () => refresh.current?.() };
}
