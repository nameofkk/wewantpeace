"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, ExternalLink, Loader2, Newspaper, Search, Send } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAdminStore, adminFetch } from "@/lib/admin-utils";
import { useAdminToast } from "@/components/ui/admin-toast";

interface Recipient {
  email: string;
  name: string;
  kind: "user" | "subscriber";
  lang: "ko" | "en";
  lang_reason: "chosen" | "hangul_name" | "pref_en" | "default" | "subscriber";
  follow: string[];
  since: string | null;
}

interface WeeklyRecipients {
  total: number;
  ko: number;
  en: number;
  members: number;
  subscribers: number;
  brief_signups: { active: number; pending: number; unsubscribed: number };
  auto_send: boolean;
  edition: {
    week: string;
    status: string;
    generated_at: string;
    stories: number;
    sent_ko_at: string | null;
    sent_en_at: string | null;
  } | null;
  history: Array<{ id: string; subject: string; sent: number; failed: number; status: string; created_at: string }>;
  items: Recipient[];
}

type SortKey = "since" | "email" | "kind" | "lang";
const PAGE_SIZE = 25;

const REASON: Record<Recipient["lang_reason"], { ko: string; en: string }> = {
  chosen: { ko: "메일에서 직접 고름", en: "Chosen in email" },
  hangul_name: { ko: "이름이 한글", en: "Korean name" },
  pref_en: { ko: "앱 설정이 영어", en: "App set to English" },
  default: { ko: "알 수 없어 영어", en: "Unknown, default English" },
  subscriber: { ko: "구독할 때 고름", en: "Chosen at signup" },
};

export default function AdminWeeklyPage() {
  const { lang } = useAdminStore();
  const ko = lang === "ko";
  const locale = ko ? "ko-KR" : "en-US";
  const { toast } = useAdminToast();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const [kindFilter, setKindFilter] = useState("");
  const [langFilter, setLangFilter] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("since");
  const [sortAsc, setSortAsc] = useState(false);
  const [page, setPage] = useState(1);

  const { data, isLoading, isError } = useQuery<WeeklyRecipients>({
    queryKey: ["admin-weekly-recipients"],
    queryFn: () => adminFetch("/admin/weekly-report/recipients"),
  });

  const testMutation = useMutation({
    mutationFn: () => adminFetch<{ sent_to: string }>("/admin/weekly-report/send-test", { method: "POST" }),
    onSuccess: (r) => toast(ko ? `${r.sent_to} 로 한국어판·영어판을 보냈습니다` : `Sent both editions to ${r.sent_to}`, "success"),
    onError: () => toast(ko ? "테스트 메일을 보내지 못했습니다" : "Test send failed", "error"),
  });

  const autoMutation = useMutation({
    mutationFn: (enabled: boolean) => adminFetch("/admin/newsletter/schedule", { method: "POST", body: { enabled } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-weekly-recipients"] }),
    onError: () => toast(ko ? "바꾸지 못했습니다" : "Update failed", "error"),
  });

  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    const list = (data?.items ?? []).filter(
      (r) =>
        (!q || r.email.includes(q) || r.name.toLowerCase().includes(q)) &&
        (!kindFilter || r.kind === kindFilter) &&
        (!langFilter || r.lang === langFilter),
    );
    const dir = sortAsc ? 1 : -1;
    return [...list].sort((a, b) => {
      const av = sortKey === "since" ? a.since ?? "" : a[sortKey];
      const bv = sortKey === "since" ? b.since ?? "" : b[sortKey];
      return av < bv ? -dir : av > bv ? dir : 0;
    });
  }, [data, search, kindFilter, langFilter, sortKey, sortAsc]);

  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const current = Math.min(page, totalPages);
  const pageRows = rows.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);

  const fmt = (iso: string | null) =>
    iso ? new Date(iso).toLocaleString(locale, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—";

  const sortHeader = (key: SortKey, label: string) => (
    <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">
      <button
        type="button"
        className="inline-flex items-center gap-1 hover:text-foreground"
        onClick={() => {
          if (sortKey === key) setSortAsc(!sortAsc);
          else { setSortKey(key); setSortAsc(key !== "since"); }
          setPage(1);
        }}
      >
        {label}
        {sortKey === key && (sortAsc ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />)}
      </button>
    </th>
  );

  if (isLoading) {
    return <div className="flex justify-center py-20"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>;
  }
  if (isError || !data) {
    return <p className="py-20 text-center text-sm text-muted-foreground">{ko ? "불러오지 못했습니다" : "Failed to load"}</p>;
  }

  const ed = data.edition;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Newspaper className="h-6 w-6 text-primary" />
            {ko ? "주간 브리핑" : "Weekly Briefing"}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {ko
              ? "매주 월요일 한국어판은 오전 7시, 영어판은 저녁 8시(한국 시간)에 나갑니다."
              : "Sent every Monday: Korean edition 07:00 KST, English edition 11:00 UTC."}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a
            href="/weekly/latest"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-sm hover:bg-secondary"
          >
            <ExternalLink className="h-4 w-4" />
            {ko ? "이번 호 웹에서 보기" : "View this edition"}
          </a>
          <button
            type="button"
            disabled={testMutation.isPending || !ed}
            onClick={() => testMutation.mutate()}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            {testMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            {ko ? "내 메일로 테스트 보내기" : "Send test to me"}
          </button>
        </div>
      </div>

      {/* 요약 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground">{ko ? "받는 사람" : "Recipients"}</p>
          <p className="mt-1 text-2xl font-bold tabular-nums">{data.total}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {ko ? `한국어판 ${data.ko} · 영어판 ${data.en}` : `Korean ${data.ko} · English ${data.en}`}
          </p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground">{ko ? "어디서 왔나" : "Source"}</p>
          <p className="mt-1 text-2xl font-bold tabular-nums">
            {data.members}
            <span className="text-sm font-normal text-muted-foreground"> {ko ? "회원" : "members"}</span>
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {ko
              ? `브리프 구독 ${data.brief_signups.active} · 확인 대기 ${data.brief_signups.pending} · 해지 ${data.brief_signups.unsubscribed}`
              : `Brief signups ${data.brief_signups.active} · pending ${data.brief_signups.pending} · unsubscribed ${data.brief_signups.unsubscribed}`}
          </p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground">{ko ? "이번 호" : "This edition"}</p>
          {ed ? (
            <>
              <p className="mt-1 text-2xl font-bold">
                {ed.week}
                <span className={cn("ml-2 rounded px-1.5 py-0.5 text-xs font-medium align-middle",
                  ed.status === "ready" ? "bg-green-500/20 text-green-400" : "bg-yellow-500/20 text-yellow-400")}>
                  {ed.status === "ready" ? (ko ? "발송 가능" : "Ready") : (ko ? "확인 필요" : "Needs review")}
                </span>
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {ko ? `기사 ${ed.stories}건 · ${fmt(ed.generated_at)} 생성` : `${ed.stories} stories · built ${fmt(ed.generated_at)}`}
              </p>
            </>
          ) : (
            <p className="mt-1 text-sm text-muted-foreground">{ko ? "아직 만들어진 호가 없습니다" : "No edition yet"}</p>
          )}
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground">{ko ? "자동 발송" : "Auto send"}</p>
          <p className={cn("mt-1 text-2xl font-bold", data.auto_send ? "text-green-400" : "text-muted-foreground")}>
            {data.auto_send ? (ko ? "켜짐" : "On") : (ko ? "꺼짐" : "Off")}
          </p>
          <button
            type="button"
            disabled={autoMutation.isPending}
            onClick={() => {
              const next = !data.auto_send;
              const msg = next
                ? (ko ? `다음 월요일부터 ${data.total}명에게 자동으로 나갑니다. 켤까요?` : `Starts sending to ${data.total} people next Monday. Turn on?`)
                : (ko ? "자동 발송을 끌까요?" : "Turn auto send off?");
              if (window.confirm(msg)) autoMutation.mutate(next);
            }}
            className="mt-1 text-xs underline text-muted-foreground hover:text-foreground disabled:opacity-50"
          >
            {data.auto_send ? (ko ? "끄기" : "Turn off") : (ko ? "켜기" : "Turn on")}
          </button>
        </div>
      </div>

      {/* 받는 사람 */}
      <div>
        <div className="flex flex-wrap items-center gap-3 mb-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              placeholder={ko ? "이메일·이름 검색" : "Search email or name"}
              className="w-64 max-w-full rounded-lg border border-border bg-card pl-8 pr-3 py-2 text-sm outline-none"
            />
          </div>
          <select
            value={kindFilter}
            onChange={(e) => { setKindFilter(e.target.value); setPage(1); }}
            className="rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none"
          >
            <option value="">{ko ? "구분 전체" : "All sources"}</option>
            <option value="user">{ko ? "회원" : "Member"}</option>
            <option value="subscriber">{ko ? "브리프 구독" : "Brief signup"}</option>
          </select>
          <select
            value={langFilter}
            onChange={(e) => { setLangFilter(e.target.value); setPage(1); }}
            className="rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none"
          >
            <option value="">{ko ? "언어판 전체" : "All editions"}</option>
            <option value="ko">{ko ? "한국어판" : "Korean"}</option>
            <option value="en">{ko ? "영어판" : "English"}</option>
          </select>
          <span className="ml-auto text-xs text-muted-foreground tabular-nums">
            {ko ? `${rows.length}명 / 전체 ${data.total}명` : `${rows.length} of ${data.total}`}
          </span>
        </div>

        <div className="rounded-xl border border-border overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-secondary/50">
              <tr>
                <th className="px-3 py-3 text-right text-xs font-medium text-muted-foreground w-12">#</th>
                {sortHeader("email", ko ? "이메일" : "Email")}
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{ko ? "이름" : "Name"}</th>
                {sortHeader("kind", ko ? "구분" : "Source")}
                {sortHeader("lang", ko ? "언어판" : "Edition")}
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{ko ? "그 언어로 보내는 이유" : "Why this edition"}</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{ko ? "고른 나라" : "Countries"}</th>
                {sortHeader("since", ko ? "수신 동의" : "Opted in")}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {pageRows.map((r, i) => (
                <tr key={r.email} className="hover:bg-secondary/20">
                  <td className="px-3 py-2.5 text-right text-xs text-muted-foreground tabular-nums">{(current - 1) * PAGE_SIZE + i + 1}</td>
                  <td className="px-3 py-2.5 font-mono text-xs">{r.email}</td>
                  <td className="px-3 py-2.5 text-xs max-w-[160px] truncate">{r.name || "—"}</td>
                  <td className="px-3 py-2.5 text-xs">{r.kind === "user" ? (ko ? "회원" : "Member") : (ko ? "브리프 구독" : "Brief signup")}</td>
                  <td className="px-3 py-2.5">
                    <span className={cn("rounded px-1.5 py-0.5 text-xs font-medium",
                      r.lang === "ko" ? "bg-blue-500/20 text-blue-400" : "bg-purple-500/20 text-purple-400")}>
                      {r.lang === "ko" ? (ko ? "한국어" : "Korean") : (ko ? "영어" : "English")}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-xs text-muted-foreground">{REASON[r.lang_reason]?.[ko ? "ko" : "en"] ?? "—"}</td>
                  <td className="px-3 py-2.5 text-xs">{r.follow.length ? r.follow.join(", ") : "—"}</td>
                  <td className="px-3 py-2.5 text-xs text-muted-foreground whitespace-nowrap">{fmt(r.since)}</td>
                </tr>
              ))}
              {pageRows.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-3 py-10 text-center text-sm text-muted-foreground">
                    {ko ? "조건에 맞는 사람이 없습니다" : "No one matches"}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="mt-3 flex items-center justify-center gap-3 text-sm">
            <button type="button" disabled={current <= 1} onClick={() => setPage(current - 1)}
              className="rounded-lg border border-border px-3 py-1.5 disabled:opacity-40">{ko ? "이전" : "Prev"}</button>
            <span className="tabular-nums text-muted-foreground">{current} / {totalPages}</span>
            <button type="button" disabled={current >= totalPages} onClick={() => setPage(current + 1)}
              className="rounded-lg border border-border px-3 py-1.5 disabled:opacity-40">{ko ? "다음" : "Next"}</button>
          </div>
        )}
      </div>

      {/* 발송 기록 */}
      <div>
        <h2 className="text-sm font-semibold mb-2">{ko ? "발송 기록" : "Send history"}</h2>
        <div className="rounded-xl border border-border overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-secondary/50">
              <tr>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{ko ? "보낸 때" : "Sent at"}</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{ko ? "제목" : "Subject"}</th>
                <th className="px-3 py-3 text-right text-xs font-medium text-muted-foreground">{ko ? "성공" : "Sent"}</th>
                <th className="px-3 py-3 text-right text-xs font-medium text-muted-foreground">{ko ? "실패" : "Failed"}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.history.map((h) => (
                <tr key={h.id}>
                  <td className="px-3 py-2.5 text-xs text-muted-foreground whitespace-nowrap">{fmt(h.created_at)}</td>
                  <td className="px-3 py-2.5 text-xs">{h.subject}</td>
                  <td className="px-3 py-2.5 text-right text-xs tabular-nums">{h.sent}</td>
                  <td className={cn("px-3 py-2.5 text-right text-xs tabular-nums", h.failed > 0 && "text-red-400")}>{h.failed}</td>
                </tr>
              ))}
              {data.history.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-3 py-8 text-center text-sm text-muted-foreground">
                    {ko ? "새 주간 브리핑은 아직 한 번도 나가지 않았습니다" : "The new weekly briefing has not been sent yet"}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
