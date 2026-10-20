/** Presentation only: missing operational values remain unavailable. */
export function durationLabel(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) return 'Unavailable';
  if (seconds === 0) return '0 min';
  if (seconds < 60) return '< 1 min';
  const minutes = Math.round(seconds / 60);
  return minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} hr${minutes % 60 ? ` ${minutes % 60} min` : ''}`;
}
export const vehicleLabel = (id: string) => id.startsWith('MALABE_PP1_') ? id.slice('MALABE_PP1_'.length) : id;
export function serviceDateLabel(value: string): string {
  const date = new Date(`${value}T12:00:00+05:30`);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('en-GB', { timeZone: 'Asia/Colombo', day: 'numeric', month: 'short', year: 'numeric' });
}
