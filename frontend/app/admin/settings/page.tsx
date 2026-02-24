"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Save, Loader2, ToggleLeft, ToggleRight } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ServiceSettings {
  maintenance_mode: boolean;
  allow_signup: boolean;
  notice_banner: string;
  pro_price: number;
  pro_plus_price: number;
}

export default function AdminSettingsPage() {
  const { user } = useAuth();
  const [settings, setSettings] = useState<ServiceSettings>({
    maintenance_mode: false,
    allow_signup: true,
    notice_banner: "",
    pro_price: 4900,
    pro_plus_price: 9900,
  });
  const [saved, setSaved] = useState(false);

  const { data, isLoading } = useQuery<ServiceSettings>({
    queryKey: ["admin-settings"],
    queryFn: async () => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/admin/settings`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("설정 로드 실패");
      return res.json();
    },
    enabled: !!user,
  });

  useEffect(() => {
    if (data) setSettings(data);
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/admin/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(settings),
      });
      if (!res.ok) throw new Error("저장 실패");
    },
    onSuccess: () => {
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  function ToggleButton({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) {
    return (
      <button onClick={() => onChange(!value)} className="focus:outline-none">
        {value
          ? <ToggleRight className="h-7 w-7 text-primary" />
          : <ToggleLeft className="h-7 w-7 text-muted-foreground" />
        }
      </button>
    );
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="p-8 max-w-2xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">서비스 설정</h1>
          <p className="text-sm text-muted-foreground mt-1">운영 설정을 변경합니다</p>
        </div>
        <button
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending}
          className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-bold text-primary-foreground disabled:opacity-50"
        >
          {saveMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : saved ? (
            "저장됨 ✓"
          ) : (
            <>
              <Save className="h-4 w-4" />
              저장
            </>
          )}
        </button>
      </div>

      <div className="space-y-4">
        {/* 점검 모드 */}
        <div className="rounded-xl border border-border bg-card p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">점검 모드</p>
              <p className="text-sm text-muted-foreground mt-0.5">활성화 시 관리자 외 서비스 접근 불가</p>
            </div>
            <ToggleButton
              value={settings.maintenance_mode}
              onChange={(v) => setSettings((s) => ({ ...s, maintenance_mode: v }))}
            />
          </div>
        </div>

        {/* 회원가입 허용 */}
        <div className="rounded-xl border border-border bg-card p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">신규 회원가입</p>
              <p className="text-sm text-muted-foreground mt-0.5">비활성화 시 새 계정 생성 차단</p>
            </div>
            <ToggleButton
              value={settings.allow_signup}
              onChange={(v) => setSettings((s) => ({ ...s, allow_signup: v }))}
            />
          </div>
        </div>

        {/* 공지 배너 */}
        <div className="rounded-xl border border-border bg-card p-5">
          <p className="font-medium mb-2">공지 배너</p>
          <textarea
            value={settings.notice_banner}
            onChange={(e) => setSettings((s) => ({ ...s, notice_banner: e.target.value }))}
            placeholder="공지 메시지 (비워두면 배너 숨김)"
            rows={3}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary resize-none"
          />
        </div>

        {/* 요금 설정 */}
        <div className="rounded-xl border border-border bg-card p-5">
          <p className="font-medium mb-3">요금 설정 (원)</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-muted-foreground">Pro 월정액</label>
              <input
                type="number"
                value={settings.pro_price}
                onChange={(e) => setSettings((s) => ({ ...s, pro_price: Number(e.target.value) }))}
                className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Pro+ 월정액</label>
              <input
                type="number"
                value={settings.pro_plus_price}
                onChange={(e) => setSettings((s) => ({ ...s, pro_plus_price: Number(e.target.value) }))}
                className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              />
            </div>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            ※ 요금 변경은 다음 결제 주기부터 적용됩니다. 기존 구독자에게 미리 공지하세요.
          </p>
        </div>
      </div>
    </div>
  );
}
