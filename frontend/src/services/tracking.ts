import type { VehiclePosition } from './api';

// Deliberately separate from apiFetch: a tracking credential is NOT the user's
// login token, and an expired device credential must not silently log in again.
export interface TrackingSample {
  sample_id:string; recorded_at:string; latitude:number; longitude:number; speed_mps:number|null;
  accuracy_m:number;
}
export class TrackingUploadError extends Error {constructor(message:string,public status:number){super(message);}}
export async function uploadTrackingPosition(credential:string,sample:TrackingSample,signal?:AbortSignal):Promise<{
  sample:VehiclePosition;duplicate:boolean;advances_latest:boolean;arrival_detection:string;operational_monitoring:string;
}>{
  const response=await fetch('/api/tracking/positions',{method:'POST',credentials:'omit',signal,
    headers:{'Content-Type':'application/json',Authorization:`Bearer ${credential}`},body:JSON.stringify(sample)});
  if(!response.ok){const body=await response.json().catch(()=>null);throw new TrackingUploadError(typeof body?.detail==='string'?body.detail:`Tracking upload rejected (${response.status}).`,response.status);}
  return response.json();
}
