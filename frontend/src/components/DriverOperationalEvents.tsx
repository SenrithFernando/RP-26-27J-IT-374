import { OperationalEvents } from '../services/api';
const time=(value:string)=>new Date(value).toLocaleString('en-GB',{timeZone:'Asia/Colombo'});
export function DriverOperationalEvents({data,error}:{data:OperationalEvents|null;error:string}) {
  const cfg=data?.settings;
  return <section aria-label="Preliminary operational events" className="rounded-lg border border-amber-200 bg-amber-50 p-3 space-y-2 text-xs text-slate-700">
    <h4 className="font-semibold">Preliminary route / movement events</h4>
    <p>Operational anomalies only, not crash or safety diagnoses. Accuracy and precision/recall targets have not been validated.</p>
    {error&&<p role="alert" className="text-red-700">Monitoring unavailable: {error}</p>}
    {!error&&!data&&<p>Loading stored monitoring evidence...</p>}
    {data&&<>
      <p>GPS: {data.gps_state} / source: {data.source??'Unknown'} / age: {data.position_age_seconds==null?'Unknown':`${Math.floor(data.position_age_seconds)} s`}</p>
      <p className="font-semibold">{data.geometry?.quality==='provider_road_geometry'?'Stored provider road geometry (structurally checked)':data.geometry?.quality==='approximate_stop_sequence'?'Approximate stop-sequence deviation - not a road route':'Geometry unavailable'}</p>
      <p>Geometry source: {data.geometry?.source??'Unavailable'}. {data.geometry?.reason}</p>
      <p>Last eligible distance to saved polyline: {data.distance_metres==null?'Unknown':`${data.distance_metres.toFixed(1)} m`}; GPS-derived step speed: {data.derived_step_speed_mps==null?'Unknown':`${data.derived_step_speed_mps.toFixed(2)} m/s`}.</p>
      {data.expected_waiting&&<p>Unexpected-stop suppression: {data.expected_waiting}</p>}
      <p>{data.gps_state==='unknown'?'GPS unknown: missing observations do not mean stopped or recovered.':data.deviation_candidate?'Sustained-deviation candidate.':data.stop_candidate?'Low-movement candidate; no stop event until thresholds hold.':'No current candidate.'}</p>
      {cfg&&<details><summary className="cursor-pointer font-semibold">Stored provisional thresholds</summary>
        <p>Deviation &gt;{cfg.selected_deviation_metres} m for {cfg.deviation_seconds} s. Recovery within {cfg.deviation_recovery_metres} m for {cfg.recovery_seconds} s.</p>
        <p>Low movement &le;{cfg.low_movement_mps} m/s inside {cfg.stop_radius_metres} m for {cfg.stop_seconds} s. Stop recovery displacement &gt;{cfg.stop_recovery_metres} m.</p>
        <p>Expected stop radius {cfg.expected_dwell_radius_metres} m; minimum {cfg.min_observations} ordered observations, maximum gap {cfg.max_gap_seconds} s, freshness {cfg.freshness_seconds} s.</p>
      </details>}
      <ol aria-label="Stored operational episodes" className="space-y-2">{data.episodes.map(event=><li key={event.id} data-episode-id={event.id} className="border-t border-amber-200 pt-2 space-y-1">
        <p className="font-semibold">{event.kind==='route_deviation'?'Route deviation':'Unexpected stop (operational)'} / {event.status} / episode {event.episode}</p>
        <p>Source: {event.source}; geometry: {event.geometry_quality} / {event.geometry_source}</p>
        <p>Evidence began: {time(event.started_at)} / Confirmed: {time(event.confirmed_at)} (Sri Lanka)</p>
        {event.recovered_at&&<p>Recovery recorded: {time(event.recovered_at)} / {event.recovery_source}</p>}
        {event.closed_at&&<p>Closed with trip: {time(event.closed_at)}; no GPS recovery implied.</p>}
        {event.recovery_reason&&<p>{event.recovery_reason}</p>}
      </li>)}</ol>
      {!data.episodes.length&&<p>No stored operational episodes for this trip.</p>}
      {data.truncated&&<p>Showing the newest stored episodes only; earlier records remain persisted.</p>}
    </>}
  </section>;
}
