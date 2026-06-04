"use client";

import { useEffect, useState } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const [isKo, setIsKo] = useState(true);

  useEffect(() => {
    console.error("Unhandled error:", error);
    setIsKo(navigator.language?.startsWith("ko") ?? true);
  }, [error]);

  return (
    <div style={{ padding: "2rem", textAlign: "center" }}>
      <h2>{isKo ? "문제가 발생했습니다" : "Something went wrong"}</h2>
      <p style={{ color: "#666", margin: "1rem 0" }}>
        {isKo ? "잠시 후 다시 시도해주세요" : "Please try again later"}
      </p>
      <button
        onClick={reset}
        style={{
          padding: "0.5rem 1.5rem",
          borderRadius: "8px",
          border: "1px solid #ddd",
          background: "#f5f5f5",
          cursor: "pointer",
        }}
      >
        {isKo ? "다시 시도" : "Try again"}
      </button>
    </div>
  );
}
