import { useEffect, useRef } from 'react';
import { useNotifications, type NotificationVariant } from './NotificationProvider';

export default function NotifyOnChange({
  value,
  variant = 'success',
  title,
  durationMs,
}: {
  value?: string | null;
  variant?: NotificationVariant;
  title?: string;
  durationMs?: number;
}) {
  const { notify } = useNotifications();
  const lastValue = useRef<string | null>(null);

  useEffect(() => {
    const next = value?.trim() || null;
    if (!next) {
      lastValue.current = null;
      return;
    }
    if (next === lastValue.current) return;
    lastValue.current = next;
    notify({ variant, title, message: next, durationMs });
  }, [durationMs, notify, title, value, variant]);

  return null;
}
