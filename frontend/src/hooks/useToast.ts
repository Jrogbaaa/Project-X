'use client';

import { useState, useCallback } from 'react';

export type ToastType = 'success' | 'info' | 'error';

export interface Toast {
  id: string;
  message: string;
  type: ToastType;
}

export interface UseToastReturn {
  toasts: Toast[];
  toast: (message: string, type?: ToastType) => void;
  dismiss: (id: string) => void;
}

export const useToast = (): UseToastReturn => {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback((message: string, type: ToastType = 'info') => {
    const id = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    
    setToasts((prev) => [...prev, { id, message, type }]);

    // Auto-dismiss after 2.5 seconds
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 2500);
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return { toasts, toast, dismiss };
};
