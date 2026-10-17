import { useEffect, useRef, useState } from 'react';
import { ApiError, fetchCurrentTrip, TripRecord, fetchLatestRoute, fetchPlanStatus, PlanStatus, RouteDirection, StoredRoute } from '../services/api';

export const DRIVER_ROUTE_POLL_MS = 15_000;
const REQUEST_TIMEOUT_MS = 12_000;
type View = { trip: TripRecord | null; tripError: string | null; key: string; route: StoredRoute | null; plan: PlanStatus | null; error: string | null;
  noRoute: boolean; refreshing: boolean; checkedAt: string | null };
const empty = (key: string): View => ({ trip: null, tripError: null, key, route: null, plan: null, error: null, noRoute: false, refreshing: false, checkedAt: null });
const message = (error: unknown) => error instanceof Error ? error.message : 'Stored route request failed.';

/** Read-only polling, serialized per selection; no generation or mutation imports. */
export function useStoredDriverRoute(vehicleId: string, direction: RouteDirection) {
  const key = `${vehicleId}:${direction}`;
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
      Promise.allSettled([fetchLatestRoute(vehicleId, direction, controller.signal), fetchPlanStatus(vehicleId, direction, controller.signal), fetchCurrentTrip(vehicleId, direction, controller.signal)])
        .then(([latest, plan, trip]) => {
          clearTimeout(currentDeadline);
          if (!alive || id !== sequence) return;
          const noRoute = latest.status === 'rejected' && latest.reason instanceof ApiError && latest.reason.status === 404;
          const errors = [latest.status === 'rejected' && !noRoute ? message(latest.reason) : null,
            plan.status === 'rejected' ? `Plan freshness could not be verified: ${message(plan.reason)}` : null].filter(Boolean);
          setView({ key, trip: trip.status === 'fulfilled' ? trip.value.trip : null,
            tripError: trip.status === 'rejected' ? `Trip state unavailable: ${message(trip.reason)}` : null, route: latest.status === 'fulfilled' ? latest.value : null,
            plan: plan.status === 'fulfilled' ? plan.value : null, noRoute, refreshing: false,
            error: timedOut ? 'Stored route request timed out. Refresh or wait for the next check.' : errors.join(' ') || null,
            checkedAt: new Date().toISOString() });
          if (document.visibilityState === 'visible') poll = setTimeout(load, DRIVER_ROUTE_POLL_MS);
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
  }, [vehicleId, direction, key]);

  return { view: view.key === key ? view : empty(key), visible, refresh: () => refresh.current?.() };
}
