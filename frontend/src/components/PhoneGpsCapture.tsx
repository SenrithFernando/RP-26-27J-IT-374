import { useEffect,useRef,useState } from 'react';
import { TrackingSample,TrackingUploadError,uploadTrackingPosition } from '../services/tracking';
import { localTime } from './PositionStatus';

export const PHONE_QUEUE_LIMIT=30,PHONE_QUEUE_TTL_MS=120000,PHONE_MAX_ATTEMPTS=5;
/** Foreground-only, in-memory queue. Credentials and coordinates never enter URLs/storage. */
export function PhoneGpsCapture({credential,expiresAt,onStatusChange}:{credential:string;expiresAt:string;onStatusChange?:(state:string)=>void}){
  const [sharing,setSharing]=useState(false),[state,setState]=useState('Ready'),[error,setError]=useState('');
  const [queued,setQueued]=useState(0),[discarded,setDiscarded]=useState(0);
  const [captureAccuracy,setCaptureAccuracy]=useState<number|null>(null);
  const [last,setLast]=useState<{recorded:string;received:string;accuracy:number|null;quality:string}|null>(null);
  const [clock,setClock]=useState(Date.now());
  const stop=useRef<(()=>void)|null>(null);
  useEffect(()=>{const timer=setInterval(()=>setClock(Date.now()),1000);return()=>clearInterval(timer);},[]);
  useEffect(()=>{
    setSharing(false);setLast(null);setState('Ready');setError('');setQueued(0);
  },[credential]);
  useEffect(()=>{
    if(!sharing)return;
    let alive=true,watch:number|undefined,inFlight=false,lastCaptured=0,nextAttempt=0;
    let queue:{sample:TrackingSample;attempts:number}[]=[];
    let controller:AbortController|undefined;
    const dropped=(count:number)=>{if(count&&alive)setDiscarded(n=>n+count);};
    const clearWatch=()=>{if(watch!==undefined){navigator.geolocation.clearWatch(watch);watch=undefined;}};
    const end=(message:string)=>{alive=false;clearWatch();controller?.abort();queue=[];setQueued(0);setState(message);setSharing(false);};
    stop.current=()=>end('Stopped; pending samples discarded');
    async function flush(){
      if(!alive||inFlight||document.visibilityState!=='visible')return;
      if(Date.now()>=Date.parse(expiresAt)){end('Tracking authorization expired');return;}
      const before=queue.length;queue=queue.filter(x=>Date.now()-Date.parse(x.sample.recorded_at)<=PHONE_QUEUE_TTL_MS&&x.attempts<PHONE_MAX_ATTEMPTS);dropped(before-queue.length);setQueued(queue.length);
      if(!queue.length||Date.now()<nextAttempt)return;
      if(!navigator.onLine){setState('Offline — bounded samples queued');return;}
      inFlight=true;const item=queue[0];item.attempts++;
      controller=new AbortController();const timeout=setTimeout(()=>controller?.abort(),8000);
      try{
        const result=await uploadTrackingPosition(credential,item.sample,controller.signal);
        if(!alive)return;
        queue=queue.filter(x=>x!==item);setQueued(queue.length);nextAttempt=0;setError('');
        setLast({recorded:result.sample.recorded_at,received:result.sample.received_at,accuracy:result.sample.accuracy_m??null,quality:result.sample.accuracy_quality??'unknown'});
        setState(result.duplicate?'Sharing — duplicate acknowledged':'Sharing — upload accepted');
      }catch(e){
        if(!alive)return;
        if(e instanceof TrackingUploadError&&[401,403,409].includes(e.status)){setError(e.message);end('Authorization or trip rejected — sharing stopped');return;}
        if(e instanceof TrackingUploadError&&e.status>=400&&e.status<500&&e.status!==429){queue=queue.filter(x=>x!==item);dropped(1);setQueued(queue.length);setError(e.message);}
        else{nextAttempt=Date.now()+Math.min(30000,2000*2**(item.attempts-1));setError('Upload unavailable; bounded retry pending. No new position is confirmed.');setState('Sharing — upload retry pending');}
      }finally{clearTimeout(timeout);inFlight=false;}
    }
    function capture(){
      if(!alive||watch!==undefined||document.visibilityState!=='visible')return;
      if(!window.isSecureContext||!navigator.geolocation){setError('Phone location requires trusted HTTPS and browser geolocation support.');end('Unavailable');return;}
      setState('Requesting location permission / waiting for GPS');
      watch=navigator.geolocation.watchPosition(position=>{
        if(!alive)return;
        const {latitude,longitude,accuracy,speed}=position.coords;
        if(![latitude,longitude,accuracy,position.timestamp].every(Number.isFinite)||accuracy<0){setError('Browser returned an invalid position.');return;}
        if(position.timestamp<=lastCaptured||position.timestamp-lastCaptured<5000)return;
        lastCaptured=position.timestamp;
        setCaptureAccuracy(accuracy);
        const sample:TrackingSample={sample_id:crypto.randomUUID(),recorded_at:new Date(position.timestamp).toISOString(),latitude,longitude,accuracy_m:accuracy,
          speed_mps:speed!=null&&Number.isFinite(speed)&&speed>=0?speed:null};
        if(queue.length>=PHONE_QUEUE_LIMIT){queue.shift();dropped(1);}
        queue.push({sample,attempts:0});setQueued(queue.length);setState('Sharing — sample captured');void flush();
      },e=>{
        if(!alive)return;
        setError(e.code===1?'Location permission denied. Allow location for this HTTPS site in Android Chrome settings.':e.code===2?'Location unavailable. Check Android location settings and GPS reception.':'GPS acquisition timed out. No location or speed was invented.');
        if(e.code===1)end('Permission denied');else setState('Sharing requested — GPS unavailable');
      },{enableHighAccuracy:true,maximumAge:0,timeout:15000});
    }
    const visibility=()=>{if(document.visibilityState==='hidden'){clearWatch();controller?.abort();setState('Paused — browser hidden; foreground required');}else{capture();void flush();}};
    const online=()=>{nextAttempt=0;void flush();};
    const timer=setInterval(()=>void flush(),2000);
    document.addEventListener('visibilitychange',visibility);window.addEventListener('online',online);capture();
    return()=>{alive=false;clearWatch();controller?.abort();clearInterval(timer);queue=[];stop.current=null;document.removeEventListener('visibilitychange',visibility);window.removeEventListener('online',online);};
  },[sharing,credential,expiresAt]);
  useEffect(()=>{onStatusChange?.(state);},[state,onStatusChange]);
  const age=last?Math.max(0,(clock-Date.parse(last.recorded))/1000):null;
  return <section aria-label="Actual phone GPS sharing" className="border rounded-lg p-3 space-y-2">
    <h4 className="font-semibold">Actual phone GPS — foreground browser</h4>
    <p role="status">Sharing state: {state}</p>{error&&<p role="alert" className="text-red-700">{error}</p>}
    <button disabled={sharing} onClick={()=>{setError('');setSharing(true);}} className="bg-[#176B87] text-white rounded px-3 py-2 disabled:opacity-40">Start sharing</button>
    <button disabled={!sharing} onClick={()=>stop.current?.()} className="ml-2 underline disabled:opacity-40">Stop sharing</button>
    <p className="text-xs text-slate-500">Pending uploads: {queued} / discarded: {discarded}</p>
    <p>Last successful upload: {localTime(last?.received)} (Sri Lanka)</p><p>Last uploaded observation: {localTime(last?.recorded)}</p>
    <p>Latest captured accuracy: {captureAccuracy==null?'Unavailable':`${captureAccuracy} m`} (browser-reported)</p>
    <p>Uploaded accuracy: {last?.accuracy==null?'Unavailable':`${last.accuracy} m`} / {last?.quality??'unknown'}</p>
    <p>Uploaded observation freshness: {age==null?'unknown':age>60?'stale':last?.quality==='poor'?'unknown — poor accuracy':'fresh'} / age {age==null?'Unavailable':`${Math.floor(age)} s`}</p>
    <p className="text-xs text-amber-900">Keep Chrome foregrounded and the screen awake. Stop sharing does not end the trip.</p>
  </section>;
}
