"use client";

import { useAuth } from "@/lib/auth";
import { useQuery } from "@tanstack/react-query";
import { Users, Flag, FileText, CreditCard, Activity, TrendingUp } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface AdminStats {
  total_users: number;
  new_today: number;
  dau: number;
  subscribers: number;
  pending_reports: number;
  monthly_revenue: number;
}

export default function AdminDashboard() {
  const { user } = useAuth();

  const { data: stats, isLoading } = useQuery<AdminStats>({
    queryKey: ["admin-stats"],
    queryFn: async () => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/admin/stats`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("통계 로드 실패");
      return res.json();
    },
    enabled: !!user,
    refetchInterval: 60_000,
  });

  const cards = [
    { label: "전체 회원", value: stats?.total_users ?? 0, icon: Users, color: "text-blue-400" },
    { label: "오늘 신규 가입", value: stats?.new_today ?? 0, icon: TrendingUp, color: "text-green-400" },
    { label: "오늘 활성 회원", value: stats?.dau ?? 0, icon: Activity, color: "text-cyan-400" },
    { label: "유료 구독자", value: stats?.subscribers ?? 0, icon: CreditCard, color: "text-yellow-400" },
    {
      label: "처리 대기 신고",
      value: stats?.pending_reports ?? 0,
      icon: Flag,
      color: (stats?.pending_reports ?? 0) > 0 ? "text-red-400" : "text-muted-foreground",
    },
    { label: "이달 매출 (원)", value: stats?.monthly_revenue ?? 0, icon: FileText, color: "text-purple-400" },
  ];

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">대시보드</h1>
        <p className="text-sm text-muted-foreground mt-1">서비스 현황 요약</p>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="rounded-xl border border-border bg-card p-5 animate-pulse">
              <div className="h-4 w-24 rounded bg-secondary mb-3" />
              <div className="h-8 w-16 rounded bg-secondary" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {cards.map((card) => (
            <div key={card.label} className="rounded-xl border border-border bg-card p-5">
              <div className="flex items-center gap-2 mb-2">
                <card.icon className={`h-4 w-4 ${card.color}`} />
                <p className="text-sm text-muted-foreground">{card.label}</p>
              </div>
              <p className="text-3xl font-bold">{card.value.toLocaleString()}</p>
            </div>
          ))}
        </div>
      )}

    </div>
  );
}
