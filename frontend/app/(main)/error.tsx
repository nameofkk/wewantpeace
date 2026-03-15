"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Unhandled error:", error);
  }, [error]);

  return (
    <div style={{ padding: "2rem", textAlign: "center" }}>
      <h2>문제가 발생했습니다</h2>
      <p style={{ color: "#666", margin: "1rem 0" }}>
        잠시 후 다시 시도해주세요
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
        다시 시도
      </button>
    </div>
  );
}
