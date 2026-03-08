"use client";

import dynamic from "next/dynamic";
import { useCallback } from "react";
import type { CallBackProps, Step, Styles } from "react-joyride";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";

const Joyride = dynamic(() => import("react-joyride"), { ssr: false });

const tourStyles: Partial<Styles> = {
  options: {
    primaryColor: "hsl(var(--primary))",
    zIndex: 10000,
    arrowColor: "hsl(var(--popover))",
    backgroundColor: "hsl(var(--popover))",
    textColor: "hsl(var(--popover-foreground))",
    overlayColor: "rgba(0, 0, 0, 0.5)",
  },
  tooltip: {
    borderRadius: "12px",
    padding: "20px",
    fontSize: "14px",
  },
  tooltipContainer: {
    textAlign: "left" as const,
  },
  buttonNext: {
    borderRadius: "8px",
    padding: "8px 16px",
    fontSize: "13px",
  },
  buttonBack: {
    color: "hsl(var(--muted-foreground))",
    fontSize: "13px",
  },
  buttonSkip: {
    color: "hsl(var(--muted-foreground))",
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
}

export default function AppTour({ tourId, steps, run }: AppTourProps) {
  const { completedTours, markTourComplete, lang } = useAppStore();
  const isCompleted = completedTours.includes(tourId);
  const shouldRun = run !== undefined ? run : !isCompleted;

  const handleCallback = useCallback(
    (data: CallBackProps) => {
      const { status } = data;
      if (status === "finished" || status === "skipped") {
        markTourComplete(tourId);
      }
    },
    [tourId, markTourComplete]
  );

  if (!shouldRun || steps.length === 0) return null;

  return (
    <Joyride
      steps={steps}
      run={shouldRun}
      continuous
      showSkipButton
      disableScrolling={false}
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
