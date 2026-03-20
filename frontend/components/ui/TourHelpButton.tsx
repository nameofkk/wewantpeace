"use client";

import { useAppStore } from "@/lib/store";

interface TourHelpButtonProps {
  tourId: string;
  onStartTour: () => void;
}

export default function TourHelpButton({ tourId, onStartTour }: TourHelpButtonProps) {
  const { resetTour } = useAppStore();

  const handleClick = () => {
    resetTour(tourId);
    onStartTour();
  };

  return (
    <button
      onClick={handleClick}
      className="fixed bottom-[calc(4.5rem+env(safe-area-inset-bottom,0px))] right-4 z-[51] flex h-11 w-11 items-center justify-center rounded-full border border-border/50 bg-background/80 text-muted-foreground/60 backdrop-blur-sm transition-colors hover:bg-accent hover:text-foreground"
      aria-label="Guide Tour"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <circle cx="12" cy="12" r="10" />
        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
        <path d="M12 17h.01" />
      </svg>
    </button>
  );
}
