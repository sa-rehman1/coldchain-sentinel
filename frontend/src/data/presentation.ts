export const present = (value: string | number | null | undefined): string => value === null || value === undefined || value === '' ? 'Unavailable' : String(value);
export const temperature = (value: number | null | undefined): string => value === null || value === undefined ? 'Unavailable' : `${value.toFixed(1)}°C`;
export const range = (minimum: number | null | undefined, maximum: number | null | undefined): string => {
  if (minimum !== null && minimum !== undefined && maximum !== null && maximum !== undefined) return `${minimum}–${maximum}°C`;
  if (maximum !== null && maximum !== undefined) return `≤${maximum}°C`;
  if (minimum !== null && minimum !== undefined) return `≥${minimum}°C`;
  return 'Unavailable';
};
export const minutes = (value: number | null | undefined): string => value === null || value === undefined ? 'Unavailable' : `${value} min`;
