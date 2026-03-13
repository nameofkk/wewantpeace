"use client";

import { useState, useEffect, useRef } from "react";

/**
 * 숫자 카운트업 애니메이션 훅.
 * 0에서 target까지 duration(ms) 동안 부드럽게 증가.
 */
export function useCountUp(target: number, duration = 800): number {
  const [value, setValue] = useState(0);
  const prevTarget = useRef(0);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    const start = prevTarget.current;
    const diff = target - start;
    if (diff === 0) return;

    const startTime = performance.now();

    function animate(now: number) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // easeOutCubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = start + diff * eased;
      setValue(Math.round(current * 10) / 10);

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      } else {
        setValue(target);
        prevTarget.current = target;
      }
    }

    rafRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target, duration]);

  return value;
}
