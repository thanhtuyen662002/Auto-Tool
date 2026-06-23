import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react';

export type NotificationVariant = 'success' | 'error' | 'info' | 'warning';

export type NotificationInput = {
  variant?: NotificationVariant;
  title?: string;
  message: string;
  durationMs?: number;
};

type NotificationItem = Required<Pick<NotificationInput, 'variant' | 'message'>> & {
  id: string;
  title: string;
  durationMs: number;
  createdAt: number;
};

type NotificationContextValue = {
  notify: (input: NotificationInput) => string;
  success: (message: string, title?: string) => string;
  error: (message: string, title?: string) => string;
  info: (message: string, title?: string) => string;
  warning: (message: string, title?: string) => string;
  dismiss: (id: string) => void;
  clear: () => void;
};

const DEFAULT_DURATION: Record<NotificationVariant, number> = {
  success: 4600,
  info: 5200,
  warning: 7000,
  error: 10000,
};

const DEFAULT_TITLE: Record<NotificationVariant, string> = {
  success: 'Thành công',
  info: 'Thông báo',
  warning: 'Cần chú ý',
  error: 'Có lỗi xảy ra',
};

const NotificationContext = createContext<NotificationContextValue | null>(null);

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const recentKeys = useRef<Map<string, number>>(new Map());

  const dismiss = useCallback((id: string) => {
    setItems((current) => current.filter((item) => item.id !== id));
  }, []);

  const notify = useCallback((input: NotificationInput) => {
    const message = friendlyNotificationText(input.message);
    if (!message) return '';
    const variant = input.variant ?? 'info';
    const title = input.title ?? DEFAULT_TITLE[variant];
    const durationMs = input.durationMs ?? DEFAULT_DURATION[variant];
    const dedupeKey = `${variant}:${title}:${message}`;
    const now = Date.now();
    const lastShownAt = recentKeys.current.get(dedupeKey) ?? 0;
    if (now - lastShownAt < 900) return '';
    recentKeys.current.set(dedupeKey, now);

    const id = `${now}-${Math.random().toString(36).slice(2, 8)}`;
    const item: NotificationItem = { id, variant, title, message, durationMs, createdAt: now };
    setItems((current) => [item, ...current].slice(0, 5));
    if (durationMs > 0) {
      window.setTimeout(() => dismiss(id), durationMs);
    }
    return id;
  }, [dismiss]);

  useEffect(() => {
    function handleNotify(event: Event) {
      const detail = (event as CustomEvent<NotificationInput>).detail;
      if (detail?.message) notify(detail);
    }
    window.addEventListener('auto-tool:notify', handleNotify);
    return () => window.removeEventListener('auto-tool:notify', handleNotify);
  }, [notify]);

  const value = useMemo<NotificationContextValue>(() => ({
    notify,
    dismiss,
    clear: () => setItems([]),
    success: (message, title) => notify({ variant: 'success', title, message }),
    error: (message, title) => notify({ variant: 'error', title, message }),
    info: (message, title) => notify({ variant: 'info', title, message }),
    warning: (message, title) => notify({ variant: 'warning', title, message }),
  }), [dismiss, notify]);

  return (
    <NotificationContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed right-4 top-20 z-[120] grid w-[min(420px,calc(100vw-2rem))] gap-3" aria-live="polite" aria-atomic="false">
        {items.map((item) => (
          <NotificationToast key={item.id} item={item} onDismiss={() => dismiss(item.id)} />
        ))}
      </div>
    </NotificationContext.Provider>
  );
}

export function useNotifications(): NotificationContextValue {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotifications must be used inside NotificationProvider');
  }
  return context;
}

export function emitNotification(input: NotificationInput) {
  window.dispatchEvent(new CustomEvent<NotificationInput>('auto-tool:notify', { detail: input }));
}

export function notificationVariantFromText(value?: string | null): NotificationVariant {
  const text = stripVietnameseMarks(value || '').toLowerCase();
  if (/\b(error|failed|fail|cannot|offline|loi|that bai|khong the|khong tai|khong mo|khong luu|khong cap nhat)\b/.test(text)) {
    return 'error';
  }
  if (/\b(canh bao|warning|chu y)\b/.test(text)) {
    return 'warning';
  }
  return 'success';
}

function NotificationToast({ item, onDismiss }: { item: NotificationItem; onDismiss: () => void }) {
  const style = toastStyle(item.variant);
  const Icon = item.variant === 'success' ? CheckCircle2 : item.variant === 'error' ? XCircle : item.variant === 'warning' ? AlertTriangle : Info;
  return (
    <div className={`pointer-events-auto overflow-hidden rounded-lg border px-4 py-3 shadow-2xl backdrop-blur-xl ${style.shell}`}>
      <div className="flex items-start gap-3">
        <Icon className={`mt-0.5 h-5 w-5 shrink-0 ${style.icon}`} />
        <div className="min-w-0 flex-1">
          <div className="notification-toast-title text-sm font-semibold">{item.title}</div>
          <div className="notification-toast-message mt-1 break-words text-sm leading-5">{item.message}</div>
        </div>
        <button
          className="notification-toast-close grid h-7 w-7 shrink-0 place-items-center rounded-md"
          type="button"
          onClick={onDismiss}
          aria-label="Đóng thông báo"
        >
          <X size={16} />
        </button>
      </div>
      {item.durationMs > 0 ? (
        <div className="notification-toast-track mt-3 h-0.5 overflow-hidden rounded-full">
          <div
            className={`h-full rounded-full ${style.bar}`}
            style={{
              animation: `notification-shrink ${item.durationMs}ms linear forwards`,
            }}
          />
        </div>
      ) : null}
    </div>
  );
}

function toastStyle(variant: NotificationVariant) {
  if (variant === 'success') {
    return {
      shell: 'notification-toast notification-toast-success',
      icon: 'notification-toast-icon notification-toast-icon-success',
      bar: 'notification-toast-bar notification-toast-bar-success',
    };
  }
  if (variant === 'error') {
    return {
      shell: 'notification-toast notification-toast-error',
      icon: 'notification-toast-icon notification-toast-icon-error',
      bar: 'notification-toast-bar notification-toast-bar-error',
    };
  }
  if (variant === 'warning') {
    return {
      shell: 'notification-toast notification-toast-warning',
      icon: 'notification-toast-icon notification-toast-icon-warning',
      bar: 'notification-toast-bar notification-toast-bar-warning',
    };
  }
  return {
    shell: 'notification-toast notification-toast-info',
    icon: 'notification-toast-icon notification-toast-icon-info',
    bar: 'notification-toast-bar notification-toast-bar-info',
  };
}

function friendlyNotificationText(value: string) {
  const text = String(value || '').trim();
  if (!text) return '';
  const firstLines = text.split(/\r?\n/).filter(Boolean).slice(0, 3).join('\n');
  return firstLines.length > 420 ? `${firstLines.slice(0, 417)}...` : firstLines;
}

function stripVietnameseMarks(value: string) {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D');
}
