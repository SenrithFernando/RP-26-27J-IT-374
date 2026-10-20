# Architecture

Runtime: frontend/src/index.tsx → App.tsx → AuthenticatedApp.tsx. AuthContext gates operations. AppContext remains for the explicitly separate demo. DriverStoredRoute, DriverTrip and useVehiclePosition reuse frontend/src/services/api.ts. Backend entry: backend/main.py. Existing persistence, providers, workers and migrations are unchanged.

Daily Plan reads dated AM/PM attendance independently. It preserves grouping, capacity, school deadlines, immutable route versions, explicit publication and fixed active-trip manifests. Date selection reads only: it never copies attendance or submits changes. Morning ends at the final school; afternoon returns to depot.

Maps distinguish optimized stop order, provider road geometry, approximate stop-sequence lines and external navigation. Google Maps receives one confirmed saved destination in latitude,longitude order, without requesting stop reordering. Its road path may differ from the saved estimate. Embedded turn-by-turn is not implemented.

Navigation now consumes the successful advance API response immediately. A delayed poll for an earlier stop cannot regress the selected destination. An arrival event must match the fixed route and current stop before enabling advancement. Missing, unconfirmed or mismatched data fails closed. Backend authorization and arrival rules remain authoritative. GPS arrival is not boarding/delivery confirmation.

Runtime import tracing found no unused frontend source/assets: proposal/demo modules remain reachable and vite-env.d.ts provides required ambient declarations. No frontend deletions were justified.
