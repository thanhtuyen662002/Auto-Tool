type ApiEnvelope<T> = {
  success?: boolean;
  data?: T;
  result?: T;
  payload?: T;
  warnings?: unknown;
  errors?: unknown;
};

export function unwrapApiResponse<T>(response: T | ApiEnvelope<T> | null | undefined): T | null {
  if (response == null) return null;
  if (typeof response !== 'object') return response as T;
  const envelope = response as ApiEnvelope<T>;
  if ('data' in envelope) return envelope.data ?? null;
  if ('result' in envelope) return envelope.result ?? null;
  if ('payload' in envelope) return envelope.payload ?? null;
  return response as T;
}

export function arrayField<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

export function numberField(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

export function objectField<T extends object>(value: unknown): T | null {
  return value && typeof value === 'object' ? (value as T) : null;
}

export function friendlyError(err: unknown, fallback = 'Không thể tải dữ liệu. Hãy thử lại sau.'): string {
  if (err instanceof Error && err.message.trim()) return err.message;
  if (typeof err === 'string' && err.trim()) return err.trim();
  return fallback;
}
