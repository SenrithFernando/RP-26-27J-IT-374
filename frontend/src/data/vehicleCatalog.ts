export interface VehicleModelPreset {
  manufacturer: string;
  model: string;
  seats: number;
  layout: {left: number;right: number;rows: number};
}

export const VEHICLE_CATALOG: Record<'School van' | 'School bus', VehicleModelPreset[]> = {
  'School van': [
    { manufacturer: 'Toyota', model: 'HiAce', seats: 12, layout: { left: 2, right: 1, rows: 4 } },
    { manufacturer: 'Nissan', model: 'Caravan', seats: 14, layout: { left: 2, right: 1, rows: 4 } },
    { manufacturer: 'Mitsubishi', model: 'Delica', seats: 10, layout: { left: 1, right: 1, rows: 5 } }
  ],
  'School bus': [
    { manufacturer: 'Toyota', model: 'Coaster', seats: 29, layout: { left: 2, right: 2, rows: 7 } },
    { manufacturer: 'Mitsubishi', model: 'Rosa', seats: 33, layout: { left: 2, right: 2, rows: 8 } },
    { manufacturer: 'Ashok Leyland', model: 'Viking', seats: 54, layout: { left: 3, right: 2, rows: 10 } }
  ]
};
