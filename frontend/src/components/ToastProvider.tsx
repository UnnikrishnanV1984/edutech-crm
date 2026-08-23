import { useCallback, useRef, useState, type ReactNode } from "react";

import { ToastContext, type ToastOptions } from "./toastContext";

interface ToastItem extends ToastOptions {
  id: number;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(0);

  const showToast = useCallback((options: ToastOptions) => {
    const id = nextId.current++;
    setToasts((current) => [...current, { ...options, id }]);
    setTimeout(() => {
      setToasts((current) => current.filter((t) => t.id !== id));
    }, 6000);
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div
        style={{
          position: "fixed",
          bottom: 16,
          left: "50%",
          transform: "translateX(-50%)",
          display: "flex",
          flexDirection: "column",
          gap: 8,
          zIndex: 1000,
        }}
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role="alert"
            style={{
              background: "var(--text-h)",
              color: "var(--bg)",
              padding: "10px 16px",
              borderRadius: "var(--radius)",
              display: "flex",
              alignItems: "center",
              gap: 12,
              fontSize: 14,
              boxShadow: "0 4px 12px rgba(0,0,0,0.2)",
            }}
          >
            <span>{toast.message}</span>
            {toast.actionLabel && toast.onAction && (
              <button
                type="button"
                onClick={toast.onAction}
                style={{ border: "none", color: "var(--accent)", padding: 0 }}
              >
                {toast.actionLabel}
              </button>
            )}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
