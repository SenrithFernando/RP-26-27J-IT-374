import { RouteStop } from '../types';

// BUS-01 morning pickup sequence. Stop 4 (Kavindu) is the stop used by the
// pickup-window demo, so the numbering here matches the driver app.
export const MORNING_STOPS: RouteStop[] = [
{ id: 'stop-m1', order: 1, location: 'Malabe', student: 'Kasun Silva', scheduledTime: '06:52', liveEta: '06:52', status: 'PICKED_UP' },
{ id: 'stop-m2', order: 2, location: 'Koswatta', student: 'Amaya Fernando', scheduledTime: '07:00', liveEta: '07:01', status: 'PICKED_UP' },
{ id: 'stop-m3', order: 3, location: 'Battaramulla', student: 'Nethmi Perera', scheduledTime: '07:08', liveEta: '07:08', status: 'PENDING' },
{ id: 'stop-m4', order: 4, location: 'Kaduwela', student: 'Kavindu Perera', scheduledTime: '07:10', liveEta: '07:14', status: 'PENDING' },
{ id: 'stop-m5', order: 5, location: 'Horizon College', student: 'Drop-off · 2 students', scheduledTime: '07:43', liveEta: '07:43', status: 'PENDING' },
{ id: 'stop-m6', order: 6, location: 'Central College', student: 'Drop-off · 2 students', scheduledTime: '07:55', liveEta: '07:55', status: 'PENDING' }];


export const AFTERNOON_STOPS: RouteStop[] = [
{ id: 'stop-a1', order: 1, location: 'Central College', student: 'Collection · 2 students', scheduledTime: '13:30', liveEta: '13:32', status: 'PENDING' },
{ id: 'stop-a2', order: 2, location: 'Horizon College', student: 'Collection · 2 students', scheduledTime: '13:45', liveEta: '13:47', status: 'PENDING' },
{ id: 'stop-a3', order: 3, location: 'Kaduwela', student: 'Kavindu Perera', scheduledTime: '14:10', liveEta: '14:13', status: 'PENDING' },
{ id: 'stop-a4', order: 4, location: 'Battaramulla', student: 'Nethmi Perera', scheduledTime: '14:18', liveEta: '14:21', status: 'PENDING' },
{ id: 'stop-a5', order: 5, location: 'Koswatta', student: 'Amaya Fernando', scheduledTime: '14:26', liveEta: '14:29', status: 'PENDING' },
{ id: 'stop-a6', order: 6, location: 'Malabe', student: 'Kasun Silva', scheduledTime: '14:35', liveEta: '14:38', status: 'PENDING' }];