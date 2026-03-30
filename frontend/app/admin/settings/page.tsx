"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Save, Loader2, Bell, Send } from "lucide-react";
import { t, type Lang } from "@/lib/i18n";
import { useAdminToast } from "@/components/ui/admin-toast";
import { cn } from "@/lib/utils";
import { useAdminStore, API_BASE } from "@/lib/admin-utils";

interface ServiceSettings {
  maintenance_mode: boolean;
  allow_signup: boolean;
  notice_banner: string;
  pro_price: number;
  pro_plus_price: number;
}

function ToggleSwitch({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!value)}
      className={cn(
        "relative inline-flex h-6 w-11 items-center rounded-full transition-colors",
        value ? "bg-primary" : "bg-secondary"
      )}
    >
      <span
        className={cn(
          "inline-block h-4 w-4 rounded-full bg-white transition-transform",
          value ? "translate-x-[24px]" : "translate-x-[4px]"
        )}
      />
    </button>
  );
}

export default function AdminSettingsPage() {
  const { user } = useAuth();
  const lang = "ko" as Lang;
  const { toast } = useAdminToast();
  const [settings, setSettings] = useState<ServiceSettings>({
    maintenance_mode: false,
    allow_signup: true,
    notice_banner: "",
    pro_price: 390,
    pro_plus_price: 690,
  });

  const { data, isLoading } = useQuery<ServiceSettings>({
    queryKey: ["admin-settings"],
    queryFn: async () => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/admin/settings`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to load settings");
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
      if (!res.ok) throw new Error("Save failed");
    },
    onSuccess: () => {
      toast(t(lang, "admin_toast_saved"), "success");
    },
    onError: () => toast(t(lang, "admin_toast_error"), "error"),
  });

  if (isLoading) {
    return (
      <div className="max-w-2xl space-y-4">
        <div className="flex justify-between items-center mb-6">
          <div className="animate-pulse space-y-2">
            <div className="h-7 w-32 rounded bg-secondary" />
            <div className="h-4 w-48 rounded bg-secondary" />
          </div>
        </div>
        {[...Array(4)].map((_, i) => (
          <div key={i} className="rounded-xl border border-border bg-card p-5 animate-pulse">
            <div className="flex justify-between items-center">
              <div className="space-y-2">
                <div className="h-4 w-24 rounded bg-secondary" />
                <div className="h-3 w-48 rounded bg-secondary" />
              </div>
              <div className="h-6 w-11 rounded-full bg-secondary" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="max-w-2xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t(lang, "admin_settings_title")}</h1>
          <p className="text-sm text-muted-foreground mt-1">{t(lang, "admin_settings_subtitle")}</p>
        </div>
        <button
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending}
          className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-bold text-primary-foreground disabled:opacity-50"
        >
          {saveMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <>
              <Save className="h-4 w-4" />
              {t(lang, "admin_save")}
            </>
          )}
        </button>
      </div>

      <div className="space-y-4">
        {/* Maintenance Mode */}
        <div className="rounded-xl border border-border bg-card p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">{t(lang, "admin_maintenance_mode")}</p>
              <p className="text-sm text-muted-foreground mt-0.5">{t(lang, "admin_maintenance_desc")}</p>
            </div>
            <ToggleSwitch
              value={settings.maintenance_mode}
              onChange={(v) => setSettings((s) => ({ ...s, maintenance_mode: v }))}
            />
          </div>
        </div>

        {/* Signup */}
        <div className="rounded-xl border border-border bg-card p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">{t(lang, "admin_signup_label")}</p>
              <p className="text-sm text-muted-foreground mt-0.5">{t(lang, "admin_signup_desc")}</p>
            </div>
            <ToggleSwitch
              value={settings.allow_signup}
              onChange={(v) => setSettings((s) => ({ ...s, allow_signup: v }))}
            />
          </div>
        </div>

        {/* Notice Banner */}
        <div className="rounded-xl border border-border bg-card p-5">
          <p className="font-medium mb-2">{t(lang, "admin_notice_banner")}</p>
          <textarea
            value={settings.notice_banner}
            onChange={(e) => setSettings((s) => ({ ...s, notice_banner: e.target.value }))}
            placeholder={t(lang, "admin_notice_placeholder")}
            rows={3}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary resize-none"
          />
        </div>

        {/* Pricing */}
        <div className="rounded-xl border border-border bg-card p-5">
          <p className="font-medium mb-3">{t(lang, "admin_pricing_label")}</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-muted-foreground">{t(lang, "admin_pricing_pro")}</label>
              <input
                type="number"
                value={settings.pro_price}
                onChange={(e) => setSettings((s) => ({ ...s, pro_price: Number(e.target.value) }))}
                className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">{t(lang, "admin_pricing_proplus")}</label>
              <input
                type="number"
                value={settings.pro_plus_price}
                onChange={(e) => setSettings((s) => ({ ...s, pro_plus_price: Number(e.target.value) }))}
                className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              />
            </div>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            {t(lang, "admin_pricing_note")}
          </p>
        </div>

        {/* Test Push */}
        <TestPushSection lang={lang} />
      </div>
    </div>
  );
}

function TestPushSection({ lang }: { lang: "ko" | "en" }) {
  const { user } = useAuth();
  const { toast } = useAdminToast();
  const [pushTitle, setPushTitle] = useState("🔔 WeWantPeace 테스트");
  const [pushBody, setPushBody] = useState("푸시 알림이 정상적으로 도착했습니다!");

  const testPushMutation = useMutation({
    mutationFn: async () => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/admin/test-push`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ title: pushTitle, body: pushBody }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Failed");
      }
      return res.json();
    },
    onSuccess: (data) => {
      const msg = t(lang, "admin_test_push_result")
        .replace("{sent}", String(data.sent))
        .replace("{total}", String(data.total_tokens))
        .replace("{cleaned}", String(data.cleaned_tokens || 0));
      toast(msg, data.sent > 0 ? "success" : "error");
    },
    onError: (err: Error) => {
      if (err.message.includes("토큰")) {
        toast(t(lang, "admin_test_push_no_token"), "error");
      } else {
        toast(err.message, "error");
      }
    },
  });

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center gap-2 mb-3">
        <Bell className="h-4 w-4 text-amber-400" />
        <p className="font-medium">{t(lang, "admin_test_push_title")}</p>
      </div>
      <p className="text-sm text-muted-foreground mb-3">{t(lang, "admin_test_push_desc")}</p>
      <div className="space-y-2">
        <div>
          <label className="text-xs text-muted-foreground">{t(lang, "admin_test_push_msg_title")}</label>
          <input
            value={pushTitle}
            onChange={(e) => setPushTitle(e.target.value)}
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground">{t(lang, "admin_test_push_msg_body")}</label>
          <input
            value={pushBody}
            onChange={(e) => setPushBody(e.target.value)}
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
          />
        </div>
        <button
          onClick={() => testPushMutation.mutate()}
          disabled={testPushMutation.isPending}
          className="flex items-center gap-2 rounded-xl bg-amber-500 px-4 py-2 text-sm font-bold text-white disabled:opacity-50 hover:bg-amber-600 transition-colors"
        >
          {testPushMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <>
              <Send className="h-4 w-4" />
              {t(lang, "admin_test_push_send")}
            </>
          )}
        </button>
      </div>
    </div>
  );
}
