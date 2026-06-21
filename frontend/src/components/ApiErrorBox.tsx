import { useEffect, useMemo, useRef } from 'react';
import GlassErrorState from './glass/GlassErrorState';
import { useNotifications } from './notifications/NotificationProvider';

interface ApiErrorBoxProps {
  error: string | null;
}

export default function ApiErrorBox({ error }: ApiErrorBoxProps) {
  const { error: notifyError } = useNotifications();
  const message = useMemo(() => (error ? friendlyError(error) : null), [error]);
  const lastMessage = useRef<string | null>(null);

  useEffect(() => {
    if (!message || message === lastMessage.current) return;
    lastMessage.current = message;
    notifyError(message);
  }, [message, notifyError]);

  if (!error) return null;
  return <GlassErrorState message={message || friendlyError(error)} />;
}

function friendlyError(error: string) {
  const firstLine = error.split(/\r?\n/).find(Boolean)?.trim() ?? error;
  return firstLine.length > 260 ? `${firstLine.slice(0, 257)}...` : firstLine;
}
