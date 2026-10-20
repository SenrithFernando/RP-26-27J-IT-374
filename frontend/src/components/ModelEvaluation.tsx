import { useEffect,useState } from 'react';
import { fetchMLStatus,MLStatus } from '../services/api';

export function ModelEvaluation(){
 const [status,setStatus]=useState<MLStatus|null>(null),[error,setError]=useState('');
 useEffect(()=>{const c=new AbortController();fetchMLStatus(c.signal).then(setStatus).catch(e=>{if(!c.signal.aborted)setError(e instanceof Error?e.message:'ML status unavailable');});return()=>c.abort();},[]);
 const evaluation=status?.evaluation;
 const number=(x:number)=>Number.isFinite(x)?x.toFixed(3):'Unavailable';
 return <details className="bg-white border rounded-xl p-4 text-sm space-y-2">
  <summary className="font-semibold cursor-pointer">Synthetic-trained ML evaluation</summary>
  <p>{error?`Status unavailable: ${error}`:status?status.available?`Loaded model: ${status.model_version}`:`Model unavailable: ${status.reason}`:'Loading model status...'}</p>
  <p>Training source: {status?.training_data_source??'Unavailable'}. This demonstrates a synthetic-data ML pipeline. Real-world accuracy has not yet been established.</p>
  {status?.available&&!evaluation&&<p>Evaluation metadata unavailable from this backend response. Restart the updated backend and refresh; no metrics are substituted.</p>}
  {evaluation&&<><p>Samples: {evaluation.sample_counts.all} total / {evaluation.sample_counts.development} development / {evaluation.sample_counts.final_test} untouched final test; {evaluation.sample_counts.all_trips} synthetic trips.</p>
   <p>{evaluation.validation_method}</p><p>{evaluation.parameter_selection}</p>
   <table className="w-full text-left"><thead><tr><th>Final test</th><th>MAE seconds / minutes</th><th>RMSE seconds / minutes</th></tr></thead><tbody>{(['xgboost','baseline'] as const).map(key=><tr key={key}><td>{key==='xgboost'?'XGBoost':'Historical-average baseline'}</td><td>{number(evaluation.final_test[key].mae_seconds)} / {number(evaluation.final_test[key].mae_minutes)}</td><td>{number(evaluation.final_test[key].rmse_seconds)} / {number(evaluation.final_test[key].rmse_minutes)}</td></tr>)}</tbody></table>
   <p>Development: {evaluation.final_test.train.samples} samples / {evaluation.final_test.train.trips} trips, {evaluation.final_test.train.start} to {evaluation.final_test.train.end}.</p>
   <p>Untouched final test: {evaluation.final_test.evaluation.samples} samples / {evaluation.final_test.evaluation.trips} trips, {evaluation.final_test.evaluation.start} to {evaluation.final_test.evaluation.end}.</p>
   <p>Final-test unseen segments: {evaluation.final_test.unseen_segment_samples}; missing weather: {evaluation.final_test.missing_weather_samples}. Unknown segments use available features; baseline fallback is the training-only global mean. Missing weather is explicitly unknown, not a forecast.</p>
   <details><summary>Chronological folds and prediction-time feature schema</summary>{evaluation.walk_forward.map(f=><p key={f.fold}>Fold {f.fold}: train {f.train.samples} ({f.train.start} to {f.train.end}); evaluation {f.evaluation.samples} ({f.evaluation.start} to {f.evaluation.end}).</p>)}<pre className="text-xs overflow-auto whitespace-pre-wrap break-words">{JSON.stringify(status?.feature_schema,null,2)}</pre></details>
  </>}
  <p>Adult geofence-exit-to-entry observations are a separate research target. These metrics are not measured phone-trip accuracy; no automatic training or dataset merging occurs.</p>
 </details>;
}
