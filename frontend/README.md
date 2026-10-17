# SafeRide-LK

SafeRide-LK is a privacy-aware school transport safety prototype for monitoring students, vehicles, routes, cabin conditions, and emergency response. It provides separate interfaces for transport administrators, drivers, parents, doctors/EMS, police, fire brigade, and hospitals.

> This is a university research prototype. Student records, GPS locations, sensor readings, incidents, responder profiles, and camera behavior are simulated unless an external stream is explicitly configured.

## Main features

### Administrator portal

- Fleet overview, live vehicle locations, routes, incidents, and notifications
- Detailed student profiles with contacts, locations, allergies, and medical information
- Trip history for every student
- Detailed vehicle registry, model-specific seating presets, and vehicle creation
- Driver and assistant profiles, daily assignments, and assignment history
- Vehicle-specific Safety Intelligence and passenger-density heatmaps
- Audited, time-limited administrator camera access
- In-app vehicle calls and emergency quick-call controls

### Driver application

- Stops, pickup windows, student checklist, RFID verification, and destination confirmation
- Full route with live ETA, traffic, and deviation warnings
- HIGH/CRITICAL alerts with tone, vibration, cause analysis, and acknowledgement
- Incoming admin/parent calls; parent calls identify the linked student
- Police, Fire & Rescue, and ambulance shortcuts

### Parent application

- Current trip, live location, progress, and child trip history
- Notifications scoped to the linked child and assigned vehicle
- Popup alerts, unread badge, and full notification history
- Red alerts remain until manually dismissed
- Automatic camera access while the child is onboard, with live occupancy
- Vehicle and emergency calling

### Emergency responders

- Separate Doctor/EMS, Police, Fire Brigade, and Hospital portals
- Sequential acknowledgement and dispatch workflow
- Responder profiles and role-specific incident information
- Secure incident camera access after the role is notified

## Vehicle presets and heatmaps

Vehicle presets include Toyota HiAce, Nissan Caravan, Mitsubishi Delica, Toyota Coaster, Mitsubishi Rosa, and Ashok Leyland Viking. Each stores its capacity, left/right seating, aisle, and row count. Safety Intelligence renders the matching passenger-density heatmap.

## Local camera stream

The administrator BUS-01 stream is configured in `src/pages/SafetyMonitoring.tsx`:

```tsx
<iframe
  src="http://192.168.0.53:8889/bus01"
  width="100%"
  height="100%"
  allow="autoplay; fullscreen"
/>
```

The browser must be on the same local network as `192.168.0.53`. An HTTPS deployment may block the HTTP iframe as mixed content. Other vehicles show a message until a stream URL is configured.

## Emergency numbers

- Police Emergency: `119`
- Fire & Rescue: `110`
- 1990 Suwa Seriya ambulance: `1990`

Use emergency numbers only when immediate assistance is required.

## Development

Requirements: Node.js 18 or newer and npm.

```bash
npm install
npm run dev
```

Open the URL printed by Vite. Choose a portal from **Choose Interface**, or use **Demo Control Center** to simulate boarding, safety, route, and crash events.

## Commands

```bash
npm run dev      # Start development server
npm run build    # Create production build
npm run preview  # Preview production build
npm run lint     # Run ESLint
```

## Technology

- React 18
- TypeScript
- Vite
- Tailwind CSS
- Lucide React

## Data and privacy notice

This prototype does not provide production authentication, encrypted video transport, persistent storage, or real emergency-service integration. A real deployment requires server-side access control, encrypted streams, consent and retention policies, tamper-resistant audit logs, secure APIs, and compliance review for children’s personal and medical data.
