export type Role = 'ADMIN' | 'DRIVER' | 'PARENT' | 'EMS' | 'POLICE' | 'FIRE' | 'HOSPITAL' | 'DEMO_CONTROL' | null;

export interface Student {
  id: string;
  name: string;
  grade: string;
  school: string;
  assignedVehicle: string;
  rfid: string;
  status: 'PLANNED' | 'BOARDED' | 'DROPPED_OFF' | 'MISSED';
  dateOfBirth: string;
  gender: string;
  parentName: string;
  relationship: string;
  primaryPhone: string;
  alternatePhone: string;
  homeAddress: string;
  pickupLocation: string;
  bloodGroup: string;
  allergies: string;
  medicalConditions: string;
  medications: string;
  emergencyNotes: string;
}

export interface Vehicle {
  id: string;
  driver: string;
  capacity: number;
  students: number;
  status: 'ACTIVE' | 'INACTIVE';
  risk: 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';
  speed: number;
  location: string;
  registrationNumber: string;
  type: string;
  manufacturer: string;
  model: string;
  makeModel: string;
  year: number;
  color: string;
  fuelType: string;
  mileageKm: number;
  insuranceExpiry: string;
  revenueLicenceExpiry: string;
  lastService: string;
  nextServiceKm: number;
  gpsDeviceId: string;
  cameraCount: number;
  emergencyKit: string;
  seatLayout: {left: number;right: number;rows: number};
}

export interface Driver {
  id: string;
  name: string;
  imageUrl: string;
  phone: string;
  email: string;
  address: string;
  nic: string;
  dateOfBirth: string;
  licenceNumber: string;
  licenceClass: string;
  licenceExpiry: string;
  experienceYears: number;
  emergencyContact: string;
  bloodGroup: string;
  medicalNotes: string;
  status: 'AVAILABLE' | 'ON_TRIP' | 'OFF_DUTY';
}

export interface Assistant {
  id: string;
  name: string;
  imageUrl: string;
  phone: string;
  nic: string;
  address: string;
  emergencyContact: string;
  joinedDate: string;
  firstAidTrained: boolean;
  status: 'AVAILABLE' | 'ON_TRIP' | 'OFF_DUTY';
}

export interface CrewAssignment {
  id: string;
  date: string;
  vehicleId: string;
  driverId: string;
  assistantId: string;
  shift: 'Morning' | 'Afternoon' | 'Full day';
  route: string;
  status: 'ASSIGNED' | 'COMPLETED' | 'REASSIGNED';
}

export interface VehicleCall {
  id: string;
  vehicleId: string;
  callerRole: 'ADMIN' | 'PARENT';
  callerName: string;
  studentName?: string;
  status: 'RINGING' | 'CONNECTED';
  startedAt: string;
}

export interface Notification {
  id: string;
  role: Role | 'ALL';
  message: string;
  time: string;
  type: 'info' | 'warning' | 'success' | 'error';
  studentId?: string;
  vehicleId?: string;
  persistent?: boolean;
}

export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';

export interface SafetyState {
  score: number;
  level: RiskLevel;
  sensors: {
    rfid: number;
    ir: number;
    pressure: number;
    ultrasonic: number;
    confidence: number;
    speed: number;
    standing: string;
    standingDuration: number;
    doorDensity: string;
    occupancy: number;
  };
  breakdown: {
    occupancy: number;
    behaviour: number;
    door: number;
    speed: number;
    sensor: number;
  };
  cameraState: 'LOCKED' | 'AVAILABLE' | 'VIEWING';
}

export interface AppState {
  role: Role;
  vehicles: Vehicle[];
  students: Student[];
  demoMode: boolean;
}

export interface RouteStop {
  id: string;
  order: number;
  location: string;
  student: string;
  scheduledTime: string;
  liveEta: string;
  status: 'PICKED_UP' | 'PENDING' | 'SKIPPED';
}

export interface RouteOptimizationResult {
  prevDistance: number;
  prevEta: number;
  newDistance: number;
  newEta: number;
}

export interface DeviationAlert {
  vehicleId: string;
  expectedRoute: string;
  distanceFromRoute: number;
  currentLocation: string;
}

export interface RouteState {
  routeTab: 'MORNING' | 'AFTERNOON';
  vehicleId: string;
  stops: RouteStop[];
  distanceKm: number;
  trafficEtaMin: number;
  mlEtaMin: number;
  combinedEtaMin: number;
  trafficLevel: 'Normal' | 'Moderate' | 'Heavy';
  isOptimizing: boolean;
  optimizationStep: number;
  lastOptimization: RouteOptimizationResult | null;
  deviationAlert: DeviationAlert | null;
}

export interface PickupWindowState {
  studentId: string;
  studentName: string;
  stopNumber: number;
  scheduledTime: string;
  windowStart: string;
  windowEnd: string;
  remainingSeconds: number;
  expired: boolean;
}

export type CrashSeverity = 'MINOR' | 'MODERATE' | 'CRITICAL';
export type DriverPhase = 'NONE' | 'COUNTDOWN' | 'SAFE' | 'TIMEOUT' | 'HELP_REQUESTED';
export type EmergencyStage =
'NONE' |
'EMS_NOTIFIED' |
'EMS_ACK' |
'POLICE_NOTIFIED' |
'POLICE_ACK' |
'FIRE_NOTIFIED' |
'FIRE_ACK' |
'HOSPITAL_NOTIFIED' |
'HOSPITAL_ACK';

export interface EmergencyTimelineEvent {
  time: string;
  label: string;
  status: 'done' | 'pending';
}

export interface CrashData {
  peakG: number;
  vehicleRoll: number;
  impactPressure: number;
  classification: CrashSeverity;
  location: string;
  time: string;
}

export interface EmergencyState {
  incidentId: string;
  active: boolean;
  severity: CrashSeverity | null;
  crashData: CrashData | null;
  driverPhase: DriverPhase;
  driverCountdown: number;
  stage: EmergencyStage;
  timeline: EmergencyTimelineEvent[];
}
