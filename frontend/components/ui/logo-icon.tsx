"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";

// logo-eye.png: 585×255px (눈만 크롭, 투명 배경)
const RATIO = 585 / 255; // ≈ 2.294

export function LogoIcon({ height = 32 }: { height?: number }) {
  const [tapped, setTapped] = useState(false);
  const width = Math.round(height * RATIO);

  const handleTap = () => {
    setTapped(true);
    setTimeout(() => setTapped(false), 250);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <Link
      href="/home"
      onClick={handleTap}
      aria-label="홈으로"
      style={{
        display: "flex",
        alignItems: "center",
        gap: "2px",           // ← gap을 style로 직접 지정
        flexShrink: 0,
        opacity: tapped ? 0.6 : 1,
        transition: "opacity 0.15s",
        pointerEvents: "auto",
        textDecoration: "none",
      }}
    >
      <div
        style={{
          position: "relative",
          width,
          height,
          flexShrink: 0,
          transform: tapped ? "scale(0.92)" : "scale(1)",
          transition: "transform 0.2s ease-out",
        }}
      >
        <Image
          src="/logo-eye.png"
          alt="WeWantPeace"
          fill
          priority
          className="object-contain"
        />
      </div>

      <span
        style={{
          fontSize: "14px",
          fontWeight: 600,
          letterSpacing: "0.02em",
          color: "inherit",
          lineHeight: 1,
          whiteSpace: "nowrap",
        }}
      >
        WeWantPeace
      </span>
    </Link>
  );
}
