import { lazy, Suspense } from 'react';
import type { RouteMapProps } from './RouteMap';

const LeafletRouteMap = lazy(() => import('./RouteMap').then((module) => ({ default: module.RouteMap })));

export function MapLoader(props: RouteMapProps) {
  return <Suspense fallback={<div role="status" className="flex items-center justify-center rounded-xl bg-slate-50 border border-slate-200 text-sm text-slate-500" style={{ height: props.height ?? 460 }}>Loading map...</div>}>
    <LeafletRouteMap {...props} />
  </Suspense>;
}
