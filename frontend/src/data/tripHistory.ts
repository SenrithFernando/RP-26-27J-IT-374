export type TripHistoryStatus = 'COMPLETED' | 'MISSED' | 'CANCELLED';

export interface TripHistoryRecord {
  id: string;
  date: string;
  trip: 'Morning pickup' | 'Afternoon drop-off';
  vehicle: string;
  driver: string;
  pickupLocation: string;
  destination: string;
  boardedAt: string;
  arrivedAt: string;
  status: TripHistoryStatus;
}

const STUDENT_VARIATIONS: Record<string, { minute: number; missedIndex?: number }> = {
  ST001: { minute: 8, missedIndex: 3 },
  ST002: { minute: 52 },
  ST003: { minute: 1, missedIndex: 5 },
  ST004: { minute: 14 },
  ST005: { minute: 18, missedIndex: 4 },
  ST006: { minute: 24 },
  ST007: { minute: 31 },
  ST008: { minute: 36, missedIndex: 2 }
};

const DATES = ['22 Aug 2026', '21 Aug 2026', '20 Aug 2026', '19 Aug 2026', '18 Aug 2026', '17 Aug 2026'];

export function getStudentTripHistory(student: {
  id: string;
  assignedVehicle: string;
  pickupLocation: string;
  school: string;
}): TripHistoryRecord[] {
  const variation = STUDENT_VARIATIONS[student.id] || { minute: 20 };
  const driver = student.assignedVehicle === 'BUS-01' ? 'D. Perera' : 'S. Fernando';

  return DATES.flatMap((date, index) => {
    const missed = variation.missedIndex === index;
    const minute = (variation.minute + index) % 60;
    const morning: TripHistoryRecord = {
      id: `${student.id}-${index}-morning`,
      date,
      trip: 'Morning pickup',
      vehicle: student.assignedVehicle,
      driver,
      pickupLocation: student.pickupLocation,
      destination: student.school,
      boardedAt: missed ? '—' : `07:${minute.toString().padStart(2, '0')}`,
      arrivedAt: missed ? '—' : `07:${(43 + index).toString().padStart(2, '0')}`,
      status: missed ? 'MISSED' : 'COMPLETED'
    };

    if (missed) return [morning];

    return [morning, {
      id: `${student.id}-${index}-afternoon`,
      date,
      trip: 'Afternoon drop-off' as const,
      vehicle: student.assignedVehicle,
      driver,
      pickupLocation: student.school,
      destination: student.pickupLocation,
      boardedAt: `13:${(32 + index).toString().padStart(2, '0')}`,
      arrivedAt: `14:${(18 + minute % 12).toString().padStart(2, '0')}`,
      status: 'COMPLETED' as const
    }];
  });
}
