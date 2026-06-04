"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { createPortal } from "react-dom";
import { Info } from "lucide-react";
import { cn } from "@/lib/utils";

interface InfoTooltipProps {
  text: string;
  /** 팝업이 열리는 방향 힌트: "up"(기본) 또는 "down" */
  direction?: "up" | "down";
  className?: string;
}

const TOOLTIP_WIDTH = 224; // w-56 = 14rem = 224px
const MARGIN = 10;          // 화면 가장자리 최소 여백

/**
 * 용어 옆에 붙이는 작은 ⓘ 버튼.
 * 데스크탑: hover, 모바일: tap 으로 팝업 토글.
 *
 * createPortal로 document.body에 렌더링 → 조상의 CSS transform/overflow 영향 없음.
 * 뷰포트 경계를 감지해 팝업이 화면 밖으로 나가지 않도록 자동 보정.
 */
export function InfoTooltip({ text, direction = "up", className }: InfoTooltipProps) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{
    left: number;
    top: number;
    dir: "up" | "down";
    tailLeft: number;
  } | null>(null);
  const [mounted, setMounted] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  // SSR 안전: 클라이언트에서만 Portal 렌더
  useEffect(() => setMounted(true), []);

  const calcPosition = useCallback(() => {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;

    // ── 상하 방향 결정 ───────────────────────────────────────────────────
    const spaceAbove = rect.top;
    const spaceBelow = window.innerHeight - rect.bottom;
    let dir: "up" | "down" = direction;
    if (direction === "up" && spaceAbove < 120) dir = "down";
    else if (direction === "down" && spaceBelow < 120) dir = "up";

    // ── 좌우 위치 (뷰포트 기준 절대좌표) ─────────────────────────────────
    const iconCenterX = rect.left + rect.width / 2;
    let left = iconCenterX - TOOLTIP_WIDTH / 2;
    if (left < MARGIN) left = MARGIN;
    if (left + TOOLTIP_WIDTH > window.innerWidth - MARGIN) {
      left = window.innerWidth - MARGIN - TOOLTIP_WIDTH;
    }

    // 꼬리 위치: 아이콘 중심에서 tooltip left 기준 offset
    const tailLeft = Math.round(iconCenterX - left);

    // ── 수직 위치 ────────────────────────────────────────────────────────
    // dir=up : 아이콘 상단 기준 위로 (transform으로 올림)
    // dir=down: 아이콘 하단 + 8px 아래
    const top = dir === "up" ? rect.top : rect.bottom + 8;

    setPos({ left, top, dir, tailLeft });
  }, [direction]);

  const handleOpen = useCallback(() => {
    calcPosition();
    setOpen(true);
  }, [calcPosition]);

  return (
    <>
      <span
        ref={ref}
        className={cn("inline-flex items-center", className)}
        onMouseEnter={handleOpen}
        onMouseLeave={() => setOpen(false)}
        onClick={(e) => {
          e.stopPropagation();
          if (open) setOpen(false);
          else handleOpen();
        }}
      >
        <Info className="h-3 w-3 cursor-help text-muted-foreground/40 hover:text-muted-foreground/80 transition-colors shrink-0" />
      </span>

      {/* Portal: document.body에 직접 렌더 → 조상 transform 영향 없음 */}
      {open && pos && mounted && createPortal(
        <span
          className={cn(
            "pointer-events-none fixed z-[9999]",
            "rounded-lg border border-border bg-card px-3 py-2.5",
            "text-[11px] leading-relaxed text-foreground shadow-xl",
            "whitespace-pre-line",
          )}
          style={{
            width: TOOLTIP_WIDTH,
            left: pos.left,
            top: pos.top,
            transform: pos.dir === "up" ? "translateY(calc(-100% - 8px))" : "none",
          }}
        >
          {text}
          {/* 말풍선 꼬리 */}
          <span
            className={cn(
              "absolute border-4 border-transparent",
              pos.dir === "up"
                ? "top-full border-t-border"
                : "bottom-full border-b-border",
            )}
            style={{
              left: pos.tailLeft,
              transform: "translateX(-50%)",
            }}
          />
        </span>,
        document.body
      )}
    </>
  );
}
