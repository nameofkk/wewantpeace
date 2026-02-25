"use client";

import { createContext, useCallback, useContext, useState } from "react";
import * as Toast from "@radix-ui/react-toast";
import { cn } from "@/lib/utils";
import { CheckCircle, AlertCircle, Info, X } from "lucide-react";

type ToastType = "success" | "error" | "info";

interface ToastItem {
  id: number;
  message: string;
  type: ToastType;
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue>({ toast: () => {} });

export function useAdminToast() {
  return useContext(ToastContext);
}

let nextId = 0;

const ICON_MAP = {
  success: CheckCircle,
  error: AlertCircle,
  info: Info,
};

const COLOR_MAP = {
  success: "border-green-500/40 bg-green-500/10 text-green-400",
  error: "border-red-500/40 bg-red-500/10 text-red-400",
  info: "border-blue-500/40 bg-blue-500/10 text-blue-400",
};

export function AdminToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const addToast = useCallback((message: string, type: ToastType = "success") => {
    const id = ++nextId;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3000);
  }, []);

  const removeToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ toast: addToast }}>
      <Toast.Provider swipeDirection="right" duration={3000}>
        {children}
        {toasts.map((item) => {
          const Icon = ICON_MAP[item.type];
          return (
            <Toast.Root
              key={item.id}
              open
              onOpenChange={(open) => { if (!open) removeToast(item.id); }}
              className={cn(
                "rounded-xl border px-4 py-3 shadow-lg flex items-center gap-3 min-w-[280px] max-w-[400px]",
                "data-[state=open]:animate-in data-[state=closed]:animate-out",
                "data-[state=open]:slide-in-from-right data-[state=closed]:slide-out-to-right",
                COLOR_MAP[item.type]
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <Toast.Description className="text-sm flex-1">
                {item.message}
              </Toast.Description>
              <Toast.Close asChild>
                <button className="opacity-60 hover:opacity-100">
                  <X className="h-3.5 w-3.5" />
                </button>
              </Toast.Close>
            </Toast.Root>
          );
        })}
        <Toast.Viewport className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 md:bottom-6 md:right-6 max-md:left-4 max-md:right-4 max-md:items-center" />
      </Toast.Provider>
    </ToastContext.Provider>
  );
}
