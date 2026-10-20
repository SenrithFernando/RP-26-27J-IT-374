import { useEffect, useState } from 'react';
import { fetchOperationalEvents, OperationalEvents, fetchPickupWindows, PickupWindows, fetchVehiclePosition, fetchTripArrival, TripArrival, LatestPosition } from '../services/api';

/** Serialized, visible-page polling. Missing GPS is unknown, never stopped. */
export function useVehiclePosition(vehicleId: string, tripId = '') {
  const key = `${vehicleId}:${tripId}`;
  const [view, setView] = useState<{ operational: OperationalEvents | null; operationalError: string; pickups: PickupWindows | null; pickupError: string; arrival: TripArrival | null; arrivalError: string; key: string; data: LatestPosition | null; error: string }>({ operational: null, operationalError: '', pickups: null, pickupError: '', arrival: null, arrivalError: '', key: '', data: null, error: '' });
  useEffect(() => {
    let alive = true, sequence = 0;
    let controller: AbortController | undefined, timer: ReturnType<typeof setTimeout> | undefined;
    let deadline: ReturnType<typeof setTimeout> | undefined;
    const cancel = () => { ++sequence; controller?.abort(); clearTimeout(timer); clearTimeout(deadline); };
    const load = async () => {
      cancel();
      if (!alive || !vehicleId || document.visibilityState !== 'visible') return;
      const id = sequence;
      controller = new AbortController();
      const request = controller;
      const timeout = setTimeout(() => request.abort(), 8000); deadline = timeout;
      try {
        const [gps, arrival, pickups, operational] = await Promise.allSettled([
          fetchVehiclePosition(vehicleId, request.signal,tripId||undefined), tripId ? fetchTripArrival(tripId, request.signal) : Promise.resolve(null),
          tripId ? fetchPickupWindows(tripId, request.signal) : Promise.resolve(null),
          tripId ? fetchOperationalEvents(tripId, request.signal) : Promise.resolve(null),
        ]);
        if (alive && id === sequence) setView({ key,
          operational: operational.status === 'fulfilled' ? operational.value : null,
          operationalError: operational.status === 'rejected' ? String(operational.reason) : '',
          pickups: pickups.status === 'fulfilled' ? pickups.value : null,
          pickupError: pickups.status === 'rejected' ? String(pickups.reason) : '',
          data: gps.status === 'fulfilled' ? gps.value : null,
          error: gps.status === 'rejected' ? String(gps.reason) : '',
          arrival: arrival.status === 'fulfilled' ? arrival.value : null,
          arrivalError: arrival.status === 'rejected' ? String(arrival.reason) : '',
        });
      } finally {
        clearTimeout(timeout);
        if (alive && id === sequence && document.visibilityState === 'visible') timer = setTimeout(load, 2000);
      }
    };
    const visibility = () => { if (document.visibilityState === 'visible') void load(); else cancel(); };
    setView({ key, operational: null, operationalError: '', pickups: null, pickupError: '', arrival: null, arrivalError: '', data: null, error: '' });
    document.addEventListener('visibilitychange', visibility); void load();
    return () => { alive = false; cancel(); document.removeEventListener('visibilitychange', visibility); };
  }, [vehicleId, tripId, key]);
  return view.key === key ? view : { key, operational: null, operationalError: '', pickups: null, pickupError: '', arrival: null, arrivalError: '', data: null, error: '' };
}
