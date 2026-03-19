"use client";

interface AvatarProps {
  nickname: string | null;
  plan?: string | null; // "free" | "pro" | "pro_plus"
  size?: "sm" | "md";
}

const PASTEL_COLORS = [
  "bg-rose-400/20 text-rose-300",
  "bg-sky-400/20 text-sky-300",
  "bg-emerald-400/20 text-emerald-300",
  "bg-amber-400/20 text-amber-300",
  "bg-violet-400/20 text-violet-300",
  "bg-teal-400/20 text-teal-300",
];

function hashNickname(name: string): number {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (hash << 5) - hash + name.charCodeAt(i);
    hash |= 0; // Convert to 32-bit integer
  }
  return Math.abs(hash);
}

const SIZE_CLASSES = {
  sm: "w-8 h-8 text-xs",
  md: "w-10 h-10 text-sm",
} as const;

export default function Avatar({ nickname, plan, size = "md" }: AvatarProps) {
  const displayChar = nickname?.trim() ? nickname.trim()[0] : "?";
  const colorIndex = nickname?.trim()
    ? hashNickname(nickname.trim()) % PASTEL_COLORS.length
    : 0;
  const colorClass = PASTEL_COLORS[colorIndex];
  const sizeClass = SIZE_CLASSES[size];

  const showBadge = plan === "pro" || plan === "pro_plus";

  return (
    <div className="relative inline-flex shrink-0">
      <div
        className={`${sizeClass} ${colorClass} rounded-full flex items-center justify-center font-bold select-none`}
      >
        {displayChar}
      </div>
      {showBadge && (
        <span
          className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-background"
          style={{
            background:
              plan === "pro_plus"
                ? "linear-gradient(135deg, #3b82f6, #8b5cf6)"
                : "linear-gradient(135deg, #fbbf24, #f59e0b)",
          }}
        />
      )}
    </div>
  );
}
