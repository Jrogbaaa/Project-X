'use client';

import { CheckCircle, Info, XCircle, X } from 'lucide-react';
import { Toast as ToastType, ToastType as ToastVariant } from '@/hooks/useToast';
import { cn } from '@/lib/utils';

interface ToastContainerProps {
  toasts: ToastType[];
  onDismiss: (id: string) => void;
}

const toastStyles: Record<ToastVariant, { bg: string; border: string; icon: typeof CheckCircle; iconColor: string; glow: string }> = {
  success: {
    bg: 'bg-metric-excellent/10',
    border: 'border-metric-excellent/30',
    icon: CheckCircle,
    iconColor: 'text-metric-excellent',
    glow: 'shadow-metric-excellent/20',
  },
  info: {
    bg: 'bg-ember-core/10',
    border: 'border-ember-core/30',
    icon: Info,
    iconColor: 'text-ember-warm',
    glow: 'shadow-ember-core/20',
  },
  error: {
    bg: 'bg-metric-poor/10',
    border: 'border-metric-poor/30',
    icon: XCircle,
    iconColor: 'text-metric-poor',
    glow: 'shadow-metric-poor/20',
  },
};

export function ToastContainer({ toasts, onDismiss }: ToastContainerProps) {
  if (toasts.length === 0) return null;

  return (
    <div 
      className="fixed bottom-6 right-6 z-50 flex flex-col gap-2"
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
              'flex items-center gap-3 px-4 py-3 rounded-xl border backdrop-blur-lg',
              'animate-slide-in-right shadow-lg min-w-[280px] max-w-[400px]',
              style.bg,
              style.border,
              style.glow
            )}
            role="alert"
          >
            <Icon className={cn('w-4 h-4 flex-shrink-0', style.iconColor)} />
            <p className="text-sm text-light-primary flex-1">{toast.message}</p>
            <button
              onClick={() => onDismiss(toast.id)}
              className="p-1 rounded-md hover:bg-white/10 transition-colors flex-shrink-0"
              aria-label="Dismiss notification"
            >
              <X className="w-3.5 h-3.5 text-light-tertiary" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
