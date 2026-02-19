'use client';

import { CheckCircle, Info, XCircle, X } from 'lucide-react';
import { Toast as ToastType, ToastType as ToastVariant } from '@/hooks/useToast';
import { cn } from '@/lib/utils';

interface ToastContainerProps {
  toasts: ToastType[];
  onDismiss: (id: string) => void;
}

const toastStyles: Record<
  ToastVariant,
  {
    bg: string;
    border: string;
    icon: typeof CheckCircle;
    iconColor: string;
  }
> = {
  success: {
    bg:        'bg-dark-secondary',
    border:    'border-metric-excellent/25',
    icon:      CheckCircle,
    iconColor: 'text-metric-excellent',
  },
  info: {
    bg:        'bg-dark-secondary',
    border:    'border-ember-warm/25',
    icon:      Info,
    iconColor: 'text-ember-warm',
  },
  error: {
    bg:        'bg-dark-secondary',
    border:    'border-metric-poor/25',
    icon:      XCircle,
    iconColor: 'text-metric-poor',
  },
};

export function ToastContainer({ toasts, onDismiss }: ToastContainerProps) {
  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed bottom-5 right-5 z-50 flex flex-col gap-2"
      role="region"
      aria-label="Notifications"
    >
      {toasts.map((toast) => {
        const style = toastStyles[toast.type];
        const Icon = style.icon;

        return (
          <div
            key={toast.id}
            className={cn(
              'flex items-center gap-3 px-4 py-3 rounded-xl border shadow-card-hover',
              'animate-slide-in-right min-w-[260px] max-w-[380px]',
              style.bg,
              style.border
            )}
            role="alert"
          >
            <Icon className={cn('w-4 h-4 flex-shrink-0', style.iconColor)} />
            <p className="text-sm text-light-primary flex-1">{toast.message}</p>
            <button
              onClick={() => onDismiss(toast.id)}
              className="p-1 rounded-md hover:bg-dark-ash transition-colors flex-shrink-0"
              aria-label="Cerrar notificación"
            >
              <X className="w-3 h-3 text-light-tertiary" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
