"use client";

import dynamic from "next/dynamic";
import { useCallback } from "react";
import type { CallBackProps, Step, Styles } from "react-joyride";
import { useAppStore } from "@/lib/store";

const Joyride = dynamic(() => import("react-joyride"), { ssr: false });

const tourStyles: Partial<Styles> = {
  options: {
    primaryColor: "#3B82F6",
    zIndex: 10000,
    arrowColor: "#1E293B",
    backgroundColor: "#1E293B",
    textColor: "#F1F5F9",
    overlayColor: "rgba(0, 0, 0, 0.6)",
  },
  tooltip: {
    borderRadius: "12px",
    padding: "20px",
    fontSize: "14px",
    maxWidth: "min(420px, 90vw)",
    wordBreak: "keep-all" as const,
    boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
    border: "1px solid rgba(255,255,255,0.1)",
  },
  tooltipContainer: {
    textAlign: "left" as const,
  },
  buttonNext: {
    borderRadius: "8px",
    padding: "8px 16px",
    fontSize: "13px",
    backgroundColor: "#3B82F6",
    color: "#FFFFFF",
  },
  buttonBack: {
    color: "#94A3B8",
    fontSize: "13px",
  },
  buttonSkip: {
    color: "#94A3B8",
    fontSize: "13px",
  },
  spotlight: {
    borderRadius: "12px",
  },
};

interface AppTourProps {
  tourId: string;
  steps: Step[];
  run?: boolean;
  onComplete?: () => void;
}

export default function AppTour({ tourId, steps, run, onComplete }: AppTourProps) {
  const { completedTours, markTourComplete, lang } = useAppStore();
  const isCompleted = completedTours.includes(tourId);
  const shouldRun = run !== undefined ? run : !isCompleted;

  const handleCallback = useCallback(
    (data: CallBackProps) => {
      const { status } = data;
      if (status === "finished" || status === "skipped") {
        markTourComplete(tourId);
        onComplete?.();
      }
    },
    [tourId, markTourComplete, onComplete]
  );

  if (!shouldRun || steps.length === 0) return null;

  return (
    <Joyride
      steps={steps}
      run={shouldRun}
      continuous
      showSkipButton
      disableScrolling={false}
      scrollOffset={200}
      spotlightClicks={false}
      callback={handleCallback}
      styles={tourStyles}
      floaterProps={{ disableAnimation: true }}
      locale={{
        back: lang === "ko" ? "이전" : "Back",
        close: lang === "ko" ? "닫기" : "Close",
        last: lang === "ko" ? "완료" : "Done",
        next: lang === "ko" ? "다음" : "Next",
        skip: lang === "ko" ? "건너뛰기" : "Skip",
      }}
    />
  );
}
