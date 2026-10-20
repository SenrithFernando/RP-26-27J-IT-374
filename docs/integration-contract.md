# Integration contract

Hasara's app/card backend remains disconnected. This boundary is API-ready, not verified end-to-end app integration. Existing authentication, object permissions, stable external IDs and validated schemas remain authoritative.

- [Provisional versioned schema](provisional-routing-contract-v1.json).
- [Saved driver route/trip contract and request examples](archive/checkpoints/hasara-driver-plan-contract-v1.md).
- [Registration/geocoding events](archive/checkpoints/registration-geocoding-checkpoint.md).
- [Boarding/window evidence handling](archive/checkpoints/boarding-window-verification.md).

GET /routes/published selects authorized vehicle, service date and direction. GET /trips/{id}/arrival reads the fixed current stop. Explicit POST /trips/{id}/advance-stop?expected_stop_sequence=N advances only after backend arrival checks. GET retrieval never solves a route. Existing frontend service types remain the exact wire contract; no parallel API was introduced.

Provider results are estimates, manual evidence is labelled test evidence, unknown attendance is not absence, and proximity does not verify passengers. Google requests remain explicitly budgeted opt-ins, never page-load actions.
