"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { t } from "@/lib/i18n";
import { useAdminStore, API_BASE } from "@/lib/admin-utils";
import { useAuth } from "@/lib/auth";
import {
  Download, Send, ChevronLeft, ChevronRight, Users, Mail,
  Award, ArrowUpRight, AlertTriangle,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface MarketingUser {
  id: string;
  email: string | null;
  nickname: string | null;
  plan: string;
  marketing_agreed_at: string | null;
}

interface EmailLog {
  id: number;
  subject: string;
  sent_count: number;
  failed_count: number;
  status: string;
  created_at: string;
}

interface ReferralKPI {
  total_codes: number;
  total_used: number;
  pro_converted: number;
  top_referrers: { user_id: string; email: string | null; nickname: string | null; referral_count: number }[];
}

function KpiCard({
  icon: Icon,
  label,
  value,
  subValue,
  color,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
  subValue?: string;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-center gap-2 mb-2">
        <div className={cn("rounded-lg p-2", color)}>
          <Icon className="h-4 w-4" />
        </div>
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      <p className="text-2xl font-bold">{typeof value === "number" ? value.toLocaleString() : value}</p>
      {subValue && <p className="text-xs text-muted-foreground mt-1">{subValue}</p>}
    </div>
  );
}

export default function AdminMarketingPage() {
  const lang = "ko" as const;
  const { user } = useAuth();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [planFilter, setPlanFilter] = useState<string>("");
  const [tab, setTab] = useState<"users" | "send" | "logs" | "referral">("users");

  // 이메일 폼
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [sendPlanFilter, setSendPlanFilter] = useState<string>("");

  const { data: usersData, isLoading } = useQuery({
    queryKey: ["admin-marketing-users", page, planFilter],
    queryFn: async () => {
      const token = await user?.getIdToken();
      const params = new URLSearchParams({ page: String(page) });
      if (planFilter) params.append("plan", planFilter);
      const res = await fetch(`${API_BASE}/admin/marketing?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed");
      return res.json() as Promise<{ total: number; items: MarketingUser[] }>;
    },
    enabled: !!user && tab === "users",
  });

  const { data: logsData } = useQuery({
    queryKey: ["admin-marketing-logs"],
    queryFn: async () => {
      const token = await user?.getIdToken();
      const res = await fetch(`${API_BASE}/admin/marketing/email-logs`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed");
      return res.json() as Promise<{ total: number; items: EmailLog[] }>;
    },
    enabled: !!user && tab === "logs",
  });

  const { data: referralData, isLoading: referralLoading } = useQuery<ReferralKPI>({
    queryKey: ["admin-reports-referral-kpi"],
    queryFn: async () => {
      const token = await user?.getIdToken();
      const res = await fetch(`${API_BASE}/admin/reports/referral-kpi`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed");
      return res.json();
    },
    enabled: !!user && tab === "referral",
  });

  const sendEmail = useMutation({
    mutationFn: async () => {
      const token = await user?.getIdToken();
      const res = await fetch(`${API_BASE}/admin/marketing/send-email`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          subject,
          body,
          plan_filter: sendPlanFilter || null,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed");
      }
      return res.json();
    },
    onSuccess: (data) => {
      alert(lang === "ko" ? `발송 완료: ${data.sent}건 성공, ${data.failed}건 실패` : `Sent: ${data.sent} success, ${data.failed} failed`);
      setSubject("");
      setBody("");
      qc.invalidateQueries({ queryKey: ["admin-marketing-logs"] });
    },
    onError: (err: Error) => {
      alert(err.message);
    },
  });

  const handleCsvDownload = async () => {
    const token = await user?.getIdToken();
    const params = new URLSearchParams();
    if (planFilter) params.append("plan", planFilter);
    const res = await fetch(`${API_BASE}/admin/marketing/export-csv?${params}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "marketing_users.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const totalPages = Math.ceil((usersData?.total ?? 0) / 20);
  const locale = lang === "en" ? "en-US" : "ko-KR";

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-lg font-bold">{t(lang, "admin_marketing")}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {lang === "ko" ? "마케팅 동의 유저 관리 및 이메일 발송" : "Manage marketing consent users and send emails"}
        </p>
      </div>

      {/* 탭 */}
      <div className="flex gap-1 mb-5 border-b border-border overflow-x-auto">
        {(["users", "send", "logs", "referral"] as const).map((t_) => (
          <button
            key={t_}
            onClick={() => setTab(t_)}
            className={cn(
              "flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap",
              tab === t_ ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            {t_ === "users" && <><Users className="h-3.5 w-3.5" />{lang === "ko" ? "유저 목록" : "Users"}</>}
            {t_ === "send" && <><Send className="h-3.5 w-3.5" />{lang === "ko" ? "이메일 발송" : "Send Email"}</>}
            {t_ === "logs" && <><Mail className="h-3.5 w-3.5" />{lang === "ko" ? "발송 이력" : "Email Logs"}</>}
            {t_ === "referral" && <><Award className="h-3.5 w-3.5" />{lang === "ko" ? "레퍼럴 KPI" : "Referral KPI"}</>}
          </button>
        ))}
      </div>

      {/* 유저 목록 탭 */}
      {tab === "users" && (
        <>
          <div className="flex items-center justify-between mb-4">
            <div className="flex gap-2">
              {["", "free", "pro", "pro_plus"].map((p) => (
                <button
                  key={p}
                  onClick={() => { setPlanFilter(p); setPage(1); }}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
                    planFilter === p ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground hover:text-foreground"
                  )}
                >
                  {p === "" ? t(lang, "admin_all") : p === "pro_plus" ? "Pro+" : p.charAt(0).toUpperCase() + p.slice(1)}
                </button>
              ))}
            </div>
            <button
              onClick={handleCsvDownload}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-secondary text-sm hover:bg-secondary/80 transition-colors"
            >
              <Download className="h-3.5 w-3.5" />
              CSV
            </button>
          </div>

          <div className="text-sm text-muted-foreground mb-3">
            {lang === "ko" ? `마케팅 동의 유저: ${usersData?.total ?? 0}명` : `Marketing consent users: ${usersData?.total ?? 0}`}
          </div>

          {isLoading ? (
            <div className="text-center py-12 text-muted-foreground">{t(lang, "admin_loading")}</div>
          ) : !usersData || usersData.items.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">{t(lang, "admin_no_data")}</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground">
                    <th className="py-2 pr-4">{t(lang, "admin_user_email")}</th>
                    <th className="py-2 pr-4">{t(lang, "admin_user_nickname")}</th>
                    <th className="py-2 pr-4">{t(lang, "admin_user_plan")}</th>
                    <th className="py-2">{lang === "ko" ? "동의일" : "Agreed"}</th>
                  </tr>
                </thead>
                <tbody>
                  {usersData.items.map((u) => (
                    <tr key={u.id} className="border-b border-border/50">
                      <td className="py-2 pr-4 text-xs">{u.email ?? "-"}</td>
                      <td className="py-2 pr-4 text-xs">{u.nickname ?? "-"}</td>
                      <td className="py-2 pr-4">
                        <span className="rounded-full bg-secondary px-2 py-0.5 text-[11px] font-medium">
                          {u.plan === "pro_plus" ? "Pro+" : u.plan.charAt(0).toUpperCase() + u.plan.slice(1)}
                        </span>
                      </td>
                      <td className="py-2 text-xs text-muted-foreground">
                        {u.marketing_agreed_at ? new Date(u.marketing_agreed_at).toLocaleDateString(locale) : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-3 mt-6">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1} className="p-1.5 rounded-lg hover:bg-secondary disabled:opacity-30">
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="text-sm text-muted-foreground">{t(lang, "admin_page_of", { page, total: totalPages })}</span>
              <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="p-1.5 rounded-lg hover:bg-secondary disabled:opacity-30">
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}
        </>
      )}

      {/* 이메일 발송 탭 */}
      {tab === "send" && (
        <div className="max-w-2xl space-y-4">
          <div>
            <label className="text-sm font-medium mb-1 block">{lang === "ko" ? "제목" : "Subject"}</label>
            <input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              placeholder={lang === "ko" ? "이메일 제목" : "Email subject"}
            />
          </div>
          <div>
            <label className="text-sm font-medium mb-1 block">{lang === "ko" ? "내용 (HTML)" : "Body (HTML)"}</label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={10}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono outline-none focus:border-primary"
              placeholder={lang === "ko" ? "<h1>안녕하세요!</h1><p>내용...</p>" : "<h1>Hello!</h1><p>Content...</p>"}
            />
          </div>
          <div>
            <label className="text-sm font-medium mb-1 block">{lang === "ko" ? "플랜 필터 (선택)" : "Plan Filter (optional)"}</label>
            <select
              value={sendPlanFilter}
              onChange={(e) => setSendPlanFilter(e.target.value)}
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm"
            >
              <option value="">{t(lang, "admin_all")}</option>
              <option value="free">Free</option>
              <option value="pro">Pro</option>
              <option value="pro_plus">Pro+</option>
            </select>
          </div>
          <button
            onClick={() => {
              if (!subject.trim() || !body.trim()) {
                alert(lang === "ko" ? "제목과 내용을 입력하세요" : "Enter subject and body");
                return;
              }
              if (!confirm(lang === "ko" ? "이메일을 발송하시겠습니까?" : "Send emails?")) return;
              sendEmail.mutate();
            }}
            disabled={sendEmail.isPending}
            className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
            {sendEmail.isPending ? (lang === "ko" ? "발송 중..." : "Sending...") : (lang === "ko" ? "이메일 발송" : "Send Email")}
          </button>
        </div>
      )}

      {/* 발송 이력 탭 */}
      {tab === "logs" && (
        <>
          {!logsData || logsData.items.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">{t(lang, "admin_no_data")}</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground">
                    <th className="py-2 pr-4">{lang === "ko" ? "시간" : "Time"}</th>
                    <th className="py-2 pr-4">{lang === "ko" ? "제목" : "Subject"}</th>
                    <th className="py-2 pr-4">{lang === "ko" ? "성공" : "Sent"}</th>
                    <th className="py-2 pr-4">{lang === "ko" ? "실패" : "Failed"}</th>
                    <th className="py-2">{t(lang, "admin_status")}</th>
                  </tr>
                </thead>
                <tbody>
                  {logsData.items.map((log) => (
                    <tr key={log.id} className="border-b border-border/50">
                      <td className="py-2.5 pr-4 text-xs text-muted-foreground whitespace-nowrap">
                        {new Date(log.created_at).toLocaleString(locale, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                      </td>
                      <td className="py-2.5 pr-4 text-xs max-w-[200px] truncate">{log.subject}</td>
                      <td className="py-2.5 pr-4 text-xs text-green-500">{log.sent_count}</td>
                      <td className="py-2.5 pr-4 text-xs text-red-400">{log.failed_count}</td>
                      <td className="py-2.5">
                        <span className={cn(
                          "rounded-full px-2 py-0.5 text-[11px] font-medium",
                          log.status === "completed" ? "bg-green-500/10 text-green-500" :
                          log.status === "failed" ? "bg-red-500/10 text-red-400" :
                          "bg-yellow-500/10 text-yellow-500"
                        )}>
                          {log.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* 레퍼럴 KPI 탭 */}
      {tab === "referral" && (
        <div>
          {referralLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="rounded-xl border border-border bg-card p-4">
                  <div className="h-4 bg-secondary/50 rounded animate-pulse w-1/2 mb-3" />
                  <div className="h-8 bg-secondary/50 rounded animate-pulse w-2/3" />
                </div>
              ))}
            </div>
          ) : referralData ? (
            <>
              {/* KPI Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
                <KpiCard
                  icon={Award}
                  label={lang === "ko" ? "총 레퍼럴 코드" : "Total Referral Codes"}
                  value={referralData.total_codes}
                  color="bg-blue-500/10 text-blue-400"
                />
                <KpiCard
                  icon={ArrowUpRight}
                  label={lang === "ko" ? "사용된 코드" : "Codes Used"}
                  value={referralData.total_used}
                  subValue={referralData.total_codes > 0
                    ? `${((referralData.total_used / referralData.total_codes) * 100).toFixed(1)}% ${lang === "ko" ? "사용률" : "usage rate"}`
                    : undefined}
                  color="bg-green-500/10 text-green-400"
                />
                <KpiCard
                  icon={AlertTriangle}
                  label={lang === "ko" ? "Pro 전환" : "Pro Converted"}
                  value={referralData.pro_converted}
                  subValue={referralData.total_used > 0
                    ? `${((referralData.pro_converted / referralData.total_used) * 100).toFixed(1)}% ${lang === "ko" ? "전환률" : "conversion rate"}`
                    : undefined}
                  color="bg-purple-500/10 text-purple-400"
                />
              </div>

              {/* Top 10 Referrers */}
              <h3 className="text-sm font-semibold mb-3">
                {lang === "ko" ? "Top 10 레퍼러" : "Top 10 Referrers"}
              </h3>

              {referralData.top_referrers.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground text-sm">
                  {lang === "ko" ? "레퍼럴 데이터 없음" : "No referral data"}
                </div>
              ) : (
                <>
                  {/* Desktop */}
                  <div className="hidden md:block rounded-xl border border-border overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-secondary/50">
                        <tr>
                          <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">#</th>
                          <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "닉네임" : "Nickname"}</th>
                          <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "이메일" : "Email"}</th>
                          <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "레퍼럴 수" : "Referrals"}</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border">
                        {referralData.top_referrers.map((r, i) => (
                          <tr key={r.user_id} className="hover:bg-secondary/20">
                            <td className="px-4 py-3 text-xs font-medium text-muted-foreground">{i + 1}</td>
                            <td className="px-4 py-3 text-xs">{r.nickname ?? "\u2014"}</td>
                            <td className="px-4 py-3 text-xs text-muted-foreground">{r.email ?? "\u2014"}</td>
                            <td className="px-4 py-3">
                              <span className="rounded-full bg-primary/10 text-primary px-2 py-0.5 text-[10px] font-medium">
                                {r.referral_count}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Mobile */}
                  <div className="md:hidden space-y-2">
                    {referralData.top_referrers.map((r, i) => (
                      <div key={r.user_id} className="flex items-center gap-3 rounded-xl border border-border bg-card p-3">
                        <span className="text-xs font-bold text-muted-foreground w-5 text-center">{i + 1}</span>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium truncate">{r.nickname ?? r.email ?? "\u2014"}</p>
                          {r.nickname && r.email && (
                            <p className="text-[10px] text-muted-foreground truncate">{r.email}</p>
                          )}
                        </div>
                        <span className="rounded-full bg-primary/10 text-primary px-2 py-0.5 text-[10px] font-medium shrink-0">
                          {r.referral_count}
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </>
          ) : (
            <div className="text-center py-12 text-muted-foreground text-sm">
              {lang === "ko" ? "데이터를 불러올 수 없습니다" : "Failed to load data"}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
