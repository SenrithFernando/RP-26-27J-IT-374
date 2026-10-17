export type SafetyEventKey =
'NORMAL' |
'OVERCROWDING' |
'STANDING_2S' |
'STANDING_12S' |
'DOOR_CROWDING' |
'SENSOR_CONFLICT' |
'HIGH_SPEED' |
'CRITICAL';

export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';

export interface SafetyScenario {
  key: SafetyEventKey;
  label: string;
  score: number;
  level: RiskLevel;
  sensors: {
    rfidCount: number;
    irCount: number;
    pressureEstimate: number;
    ultrasonicEstimate: number;
    confidence: number;
    speed: number;
    vehicleStatus: string;
    standingStudent: string;
    standingDuration: number;
    doorDensity: 'Normal' | 'Moderate' | 'High';
    roadCondition: string;
    occupancy: number;
    capacity: number;
  };
  breakdown: {
    occupancy: number;
    behaviour: number;
    doorCrowding: number;
    speed: number;
    sensorDisagreement: number;
  };
  alertTitle?: string;
  alertBody?: string;
}

export const SAFETY_SCENARIOS: Record<SafetyEventKey, SafetyScenario> = {
  NORMAL: {
    key: 'NORMAL',
    label: 'Normal',
    score: 18,
    level: 'LOW',
    sensors: { rfidCount: 8, irCount: 8, pressureEstimate: 9, ultrasonicEstimate: 8, confidence: 94, speed: 34, vehicleStatus: 'Moving', standingStudent: 'None', standingDuration: 0, doorDensity: 'Normal', roadCondition: 'Normal', occupancy: 8, capacity: 15 },
    breakdown: { occupancy: 5, behaviour: 0, doorCrowding: 0, speed: 8, sensorDisagreement: 5 }
  },
  OVERCROWDING: {
    key: 'OVERCROWDING',
    label: 'Overcrowding',
    score: 45,
    level: 'MODERATE',
    sensors: { rfidCount: 15, irCount: 14, pressureEstimate: 15, ultrasonicEstimate: 13, confidence: 89, speed: 30, vehicleStatus: 'Moving', standingStudent: '2 students', standingDuration: 4, doorDensity: 'Moderate', roadCondition: 'Normal', occupancy: 15, capacity: 15 },
    breakdown: { occupancy: 25, behaviour: 0, doorCrowding: 10, speed: 5, sensorDisagreement: 5 },
    alertTitle: 'Overcrowding Detected',
    alertBody: 'BUS-01 is at full capacity with standing passengers.'
  },
  STANDING_2S: {
    key: 'STANDING_2S',
    label: 'Standing 2 sec',
    score: 38,
    level: 'MODERATE',
    sensors: { rfidCount: 8, irCount: 8, pressureEstimate: 8, ultrasonicEstimate: 8, confidence: 92, speed: 32, vehicleStatus: 'Moving', standingStudent: 'Kasun Silva', standingDuration: 2, doorDensity: 'Normal', roadCondition: 'Normal', occupancy: 8, capacity: 15 },
    breakdown: { occupancy: 5, behaviour: 20, doorCrowding: 0, speed: 8, sensorDisagreement: 5 },
    alertTitle: 'Standing Detected',
    alertBody: 'A student is standing while the vehicle is moving.'
  },
  STANDING_12S: {
    key: 'STANDING_12S',
    label: 'Standing 12 sec',
    score: 72,
    level: 'HIGH',
    sensors: { rfidCount: 8, irCount: 8, pressureEstimate: 8, ultrasonicEstimate: 7, confidence: 90, speed: 38, vehicleStatus: 'Moving', standingStudent: 'Kasun Silva', standingDuration: 12, doorDensity: 'Moderate', roadCondition: 'Normal', occupancy: 8, capacity: 15 },
    breakdown: { occupancy: 5, behaviour: 45, doorCrowding: 5, speed: 12, sensorDisagreement: 5 },
    alertTitle: 'Unsafe Behaviour',
    alertBody: 'Standing while vehicle moving for 12 seconds at 38 km/h.'
  },
  DOOR_CROWDING: {
    key: 'DOOR_CROWDING',
    label: 'Door Crowding',
    score: 64,
    level: 'HIGH',
    sensors: { rfidCount: 8, irCount: 8, pressureEstimate: 9, ultrasonicEstimate: 8, confidence: 91, speed: 22, vehicleStatus: 'Slowing', standingStudent: '3 students', standingDuration: 6, doorDensity: 'High', roadCondition: 'Normal', occupancy: 8, capacity: 15 },
    breakdown: { occupancy: 10, behaviour: 0, doorCrowding: 40, speed: 9, sensorDisagreement: 5 },
    alertTitle: 'Door Area Crowding',
    alertBody: '5 passengers detected in the door zone.'
  },
  SENSOR_CONFLICT: {
    key: 'SENSOR_CONFLICT',
    label: 'Sensor Conflict',
    score: 42,
    level: 'MODERATE',
    sensors: { rfidCount: 8, irCount: 11, pressureEstimate: 6, ultrasonicEstimate: 10, confidence: 58, speed: 30, vehicleStatus: 'Moving', standingStudent: 'Unknown', standingDuration: 0, doorDensity: 'Normal', roadCondition: 'Normal', occupancy: 8, capacity: 15 },
    breakdown: { occupancy: 5, behaviour: 0, doorCrowding: 0, speed: 7, sensorDisagreement: 30 },
    alertTitle: 'Sensor Disagreement',
    alertBody: 'RFID, IR, pressure and ultrasonic estimates disagree.'
  },
  HIGH_SPEED: {
    key: 'HIGH_SPEED',
    label: 'High Speed',
    score: 68,
    level: 'HIGH',
    sensors: { rfidCount: 8, irCount: 8, pressureEstimate: 9, ultrasonicEstimate: 8, confidence: 93, speed: 62, vehicleStatus: 'Moving Fast', standingStudent: 'None', standingDuration: 0, doorDensity: 'Normal', roadCondition: 'Normal', occupancy: 8, capacity: 15 },
    breakdown: { occupancy: 5, behaviour: 0, doorCrowding: 0, speed: 55, sensorDisagreement: 8 },
    alertTitle: 'High Speed Detected',
    alertBody: 'BUS-01 is travelling at 62 km/h, above the safe threshold.'
  },
  CRITICAL: {
    key: 'CRITICAL',
    label: 'Critical Risk',
    score: 92,
    level: 'CRITICAL',
    sensors: { rfidCount: 15, irCount: 13, pressureEstimate: 16, ultrasonicEstimate: 12, confidence: 81, speed: 45, vehicleStatus: 'Moving', standingStudent: '4 students', standingDuration: 20, doorDensity: 'High', roadCondition: 'Uneven', occupancy: 15, capacity: 15 },
    breakdown: { occupancy: 15, behaviour: 35, doorCrowding: 22, speed: 15, sensorDisagreement: 5 },
    alertTitle: 'Critical Safety Risk',
    alertBody: 'Multiple compounding risk factors detected on BUS-01.'
  }
};

export function getRiskColor(level: RiskLevel) {
  switch (level) {
    case 'LOW':return { text: 'text-[#22C55E]', bg: 'bg-[#22C55E]', bgSoft: 'bg-green-50', border: 'border-green-200' };
    case 'MODERATE':return { text: 'text-[#F59E0B]', bg: 'bg-[#F59E0B]', bgSoft: 'bg-amber-50', border: 'border-amber-200' };
    case 'HIGH':return { text: 'text-[#F97316]', bg: 'bg-[#F97316]', bgSoft: 'bg-orange-50', border: 'border-orange-200' };
    case 'CRITICAL':return { text: 'text-[#DC2626]', bg: 'bg-[#DC2626]', bgSoft: 'bg-red-50', border: 'border-red-200' };
  }
}