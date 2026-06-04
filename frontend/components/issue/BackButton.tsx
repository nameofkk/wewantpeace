"use client";

import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";

export function BackButton() {
  const router = useRouter();
  return (
    <button
      onClick={() => router.back()}
      className="rounded-lg p-1.5 min-h-[44px] min-w-[44px] flex items-center justify-center hover:bg-secondary transition-colors"
    >
      <ArrowLeft className="h-5 w-5" />
    </button>
  );
}
