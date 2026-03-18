"use client";

import { useState, useRef, useCallback } from "react";
import { useAppStore } from "@/lib/store";
import { t, getTensionLevelLabel } from "@/lib/i18n";
import { getCountryName, getFlag } from "@/lib/countries";
import { cn } from "@/lib/utils";
import { adminFetch } from "@/lib/admin-utils";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAdminToast } from "@/components/ui/admin-toast";
import { TabBar } from "@/components/admin/TabBar";
import { StatCard } from "@/components/admin/StatCard";
import {
  Eye, Edit3, Clock, Send, TestTube, BarChart3, Layers,
  AlertTriangle, GripVertical, X, RotateCcw, Mail, Loader2,
} from "lucide-react";

/* ── Types ── */
interface IssueItem {
  id: string;
  title: string;
  title_ko: string | null;
  severity: number;
  kscore: number;
  event_count: number;
  country_code: string | null;
  topic: string;
}

interface TensionItem {
  country_code: string;
  raw_score: number;
  tension_level: number;
}

interface DraftData {
  week: string;
  editor_note_ko: string;
  editor_note_en: string;
  top_issues: IssueItem[];
  all_issues: IssueItem[];
  top_tension: TensionItem[];
  stats: { total_events: number; new_clusters: number; crisis_countries: number };
  target_count: number;
}

interface HistoryItem {
  id: number;
  date: string;
  sent: number;
  failed: number;
  status: string;
}

const SEVERITY_COLORS: Record<string, string> = {
  extreme: "border-l-red-800",
  severe: "border-l-red-500",
  warning: "border-l-orange-500",
  caution: "border-l-amber-500",
  stable: "border-l-green-500",
};

function severityClass(s: number) {
  if (s >= 80) return SEVERITY_COLORS.extreme;
  if (s >= 60) return SEVERITY_COLORS.severe;
  if (s >= 40) return SEVERITY_COLORS.warning;
  if (s >= 20) return SEVERITY_COLORS.caution;
  return SEVERITY_COLORS.stable;
}

const TENSION_BAR_COLORS: Record<number, string> = {
  0: "bg-green-500", 1: "bg-amber-500", 2: "bg-orange-500", 3: "bg-red-500", 4: "bg-red-800",
};

const TOPIC_KO: Record<string, string> = {
  conflict: "무장 충돌", terror: "폭력·테러", coup: "정변·쿠데타",
  sanctions: "경제 제재", cyber: "사이버 공격", protest: "시위·집회",
  diplomacy: "외교", maritime: "해상 분쟁", disaster: "재난·재해",
  health: "감염병·보건", unknown: "이슈",
};

function WowDelta({ current, previous }: { current: number; previous: number }) {
  if (!previous || previous === 0) return null;
  const diff = current - previous;
  const pct = Math.round((diff / previous) * 100);
  return (
    <span className={cn("text-xs font-bold tabular-nums ml-1", diff > 0 ? "text-red-500" : diff < 0 ? "text-emerald-500" : "text-muted-foreground")}>
      {diff > 0 ? "+" : ""}{pct}%
    </span>
  );
}

/* ── Tab 1: Preview ── */
function ReportPreview({ data }: { data: DraftData }) {
  const lang = useAppStore((s) => s.lang);

  return (
    <div className="space-y-6">
      {/* Editor note */}
      {(data.editor_note_ko || data.editor_note_en) && (
        <div className="rounded-xl border border-blue-500/30 bg-blue-500/5 p-4">
          <p className="text-xs font-semibold text-blue-400 mb-1">{t(lang, "admin_wr_editor_note")}</p>
          <p className="text-sm text-foreground whitespace-pre-wrap">
            {lang === "ko" ? (data.editor_note_ko || data.editor_note_en) : (data.editor_note_en || data.editor_note_ko)}
          </p>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard label={t(lang, "weekly_report_total_events")} value={data.stats.total_events} icon={BarChart3} iconColor="text-blue-400" iconBg="bg-blue-500/10" />
        <StatCard label={t(lang, "weekly_report_new_clusters")} value={data.stats.new_clusters} icon={Layers} iconColor="text-emerald-400" iconBg="bg-emerald-500/10" />
        <StatCard label={t(lang, "weekly_report_crisis_countries")} value={data.stats.crisis_countries} icon={AlertTriangle} iconColor={data.stats.crisis_countries > 0 ? "text-red-400" : "text-muted-foreground"} iconBg={data.stats.crisis_countries > 0 ? "bg-red-500/10" : "bg-secondary"} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* TOP Issues */}
        <div>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            {t(lang, "weekly_report_top_issues")}
          </h2>
          <div className="space-y-2">
            {data.top_issues.map((issue, idx) => {
              const title = lang === "en" ? issue.title : (issue.title_ko ?? issue.title);
              const topicLabel = lang === "ko" ? (TOPIC_KO[issue.topic] || issue.topic) : issue.topic;
              return (
                <div key={issue.id} className={cn("flex items-start gap-3 rounded-xl border bg-card p-3 border-l-[3px]", severityClass(issue.severity))}>
                  <span className="text-xs font-bold text-muted-foreground tabular-nums w-5 shrink-0 pt-0.5">{idx + 1}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold leading-snug line-clamp-2">{title}</p>
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mt-1.5 text-[11px] text-muted-foreground">
                      {issue.country_code && <span>{getFlag(issue.country_code)} {getCountryName(issue.country_code, lang)}</span>}
                      <span>{topicLabel}</span>
                      <span>Sev {issue.severity}</span>
                      <span>K {issue.kscore.toFixed(1)}</span>
                      <span>{issue.event_count} events</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* TOP Tension */}
        <div>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            {t(lang, "weekly_report_tension_rank")}
          </h2>
          <div className="space-y-2">
            {data.top_tension.map((item, idx) => {
              const barWidth = Math.max(item.raw_score, 5);
              const levelLabel = getTensionLevelLabel(item.tension_level as 0 | 1 | 2 | 3 | 4, lang);
              return (
                <div key={item.country_code} className="flex items-center gap-3 rounded-lg border border-border bg-card p-3">
                  <span className="text-xs font-bold text-muted-foreground tabular-nums w-5 shrink-0">{idx + 1}</span>
                  <span className="text-sm shrink-0">{getFlag(item.country_code)}</span>
                  <span className="text-sm font-medium w-24 shrink-0 truncate">{getCountryName(item.country_code, lang)}</span>
                  <div className="flex-1 h-5 bg-secondary rounded-full overflow-hidden">
                    <div className={cn("h-full rounded-full transition-all", TENSION_BAR_COLORS[item.tension_level] ?? "bg-gray-500")} style={{ width: `${barWidth}%` }} />
                  </div>
                  <span className="text-xs font-bold tabular-nums w-10 text-right">{item.raw_score.toFixed(1)}</span>
                  <span className="text-[10px] text-muted-foreground w-10 shrink-0">{levelLabel}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Tab 2: Editor ── */
function ReportEditor({ data, onSaved }: { data: DraftData; onSaved: () => void }) {
  const lang = useAppStore((s) => s.lang);
  const { toast } = useAdminToast();
  const [noteKo, setNoteKo] = useState(data.editor_note_ko);
  const [noteEn, setNoteEn] = useState(data.editor_note_en);
  const [issueIds, setIssueIds] = useState<string[]>(data.top_issues.map((i) => i.id));
  const [excluded, setExcluded] = useState<string[]>([]);
  const dragItem = useRef<number | null>(null);
  const dragOver = useRef<number | null>(null);

  const allIssueMap = Object.fromEntries(data.all_issues.map((i) => [i.id, i]));

  const saveDraft = useMutation({
    mutationFn: () => adminFetch("/admin/weekly-report/draft", {
      method: "PUT",
      body: { editor_note_ko: noteKo, editor_note_en: noteEn, issue_ids: issueIds },
    }),
    onSuccess: () => {
      toast(t(lang, "admin_wr_draft_saved"), "success");
      onSaved();
    },
    onError: () => toast(t(lang, "admin_toast_error"), "error"),
  });

  const handleDragStart = (idx: number) => { dragItem.current = idx; };
  const handleDragEnter = (idx: number) => { dragOver.current = idx; };
  const handleDragEnd = () => {
    if (dragItem.current === null || dragOver.current === null) return;
    const copy = [...issueIds];
    const [moved] = copy.splice(dragItem.current, 1);
    copy.splice(dragOver.current, 0, moved);
    setIssueIds(copy);
    dragItem.current = null;
    dragOver.current = null;
  };

  const handleExclude = (id: string) => {
    setIssueIds((prev) => prev.filter((i) => i !== id));
    setExcluded((prev) => [...prev, id]);
  };

  const handleRestore = (id: string) => {
    setExcluded((prev) => prev.filter((i) => i !== id));
    setIssueIds((prev) => [...prev, id]);
  };

  return (
    <div className="space-y-6">
      {/* Editor notes */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          <label className="text-xs font-medium text-muted-foreground mb-1 block">{t(lang, "admin_wr_editor_note_ko")}</label>
          <textarea
            value={noteKo}
            onChange={(e) => setNoteKo(e.target.value)}
            placeholder={t(lang, "admin_wr_editor_note_placeholder")}
            className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none focus:border-primary min-h-[100px] resize-y"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground mb-1 block">{t(lang, "admin_wr_editor_note_en")}</label>
          <textarea
            value={noteEn}
            onChange={(e) => setNoteEn(e.target.value)}
            placeholder="Write a note or comment for this week..."
            className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none focus:border-primary min-h-[100px] resize-y"
          />
        </div>
      </div>

      {/* Issue reorder */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold">TOP {issueIds.length} {lang === "ko" ? "이슈" : "Issues"}</h3>
          <p className="text-xs text-muted-foreground">{t(lang, "admin_wr_drag_reorder")}</p>
        </div>
        <div className="space-y-1">
          {issueIds.map((id, idx) => {
            const issue = allIssueMap[id];
            if (!issue) return null;
            const title = lang === "ko" ? (issue.title_ko ?? issue.title) : issue.title;
            return (
              <div
                key={id}
                draggable
                onDragStart={() => handleDragStart(idx)}
                onDragEnter={() => handleDragEnter(idx)}
                onDragEnd={handleDragEnd}
                onDragOver={(e) => e.preventDefault()}
                className="flex items-center gap-2 rounded-lg border border-border bg-card p-2 cursor-grab active:cursor-grabbing hover:border-primary/30"
              >
                <GripVertical className="h-4 w-4 text-muted-foreground shrink-0" />
                <span className="text-xs font-bold text-muted-foreground tabular-nums w-5">{idx + 1}</span>
                <span className="text-sm truncate flex-1">{title}</span>
                <span className="text-xs text-muted-foreground tabular-nums shrink-0">Sev {issue.severity} · K {issue.kscore.toFixed(1)}</span>
                <button onClick={() => handleExclude(id)} className="text-muted-foreground hover:text-red-400 shrink-0">
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Excluded */}
      {excluded.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-muted-foreground mb-2">{t(lang, "admin_wr_exclude")}d ({excluded.length})</h3>
          <div className="space-y-1">
            {excluded.map((id) => {
              const issue = allIssueMap[id];
              if (!issue) return null;
              return (
                <div key={id} className="flex items-center gap-2 rounded-lg border border-border bg-card/50 p-2 opacity-60">
                  <span className="text-sm truncate flex-1">{lang === "ko" ? (issue.title_ko ?? issue.title) : issue.title}</span>
                  <button onClick={() => handleRestore(id)} className="text-xs text-primary hover:underline flex items-center gap-1">
                    <RotateCcw className="h-3 w-3" /> {t(lang, "admin_wr_restore")}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Save */}
      <button
        onClick={() => saveDraft.mutate()}
        disabled={saveDraft.isPending}
        className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
      >
        {saveDraft.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
        {t(lang, "admin_wr_save_draft")}
      </button>
    </div>
  );
}

/* ── Tab 3: History ── */
function ReportHistory() {
  const lang = useAppStore((s) => s.lang);
  const locale = lang === "en" ? "en-US" : "ko-KR";

  const { data, isLoading } = useQuery<HistoryItem[]>({
    queryKey: ["admin-weekly-report-history"],
    queryFn: () => adminFetch<HistoryItem[]>("/admin/weekly-report/history"),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="h-6 w-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!data?.length) {
    return (
      <div className="flex flex-col items-center py-16 text-muted-foreground">
        <Clock className="h-10 w-10 mb-3" />
        <p className="text-sm">{t(lang, "admin_wr_no_history")}</p>
      </div>
    );
  }

  const STATUS_COLORS: Record<string, string> = {
    completed: "bg-green-500/20 text-green-400",
    failed: "bg-red-500/20 text-red-400",
    sending: "bg-amber-500/20 text-amber-400",
  };

  return (
    <div className="rounded-xl border border-border overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-secondary/50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_wr_history_date")}</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_wr_history_sent")}</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_wr_history_failed")}</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_wr_history_status")}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {data.map((item) => (
            <tr key={item.id} className="hover:bg-secondary/20">
              <td className="px-4 py-3 text-sm">
                {item.date ? new Date(item.date).toLocaleString(locale, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "\u2014"}
              </td>
              <td className="px-4 py-3 text-sm tabular-nums">{item.sent}</td>
              <td className="px-4 py-3 text-sm tabular-nums">{item.failed > 0 ? <span className="text-red-400">{item.failed}</span> : 0}</td>
              <td className="px-4 py-3">
                <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-bold", STATUS_COLORS[item.status] ?? "bg-secondary text-muted-foreground")}>
                  {item.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ── Send Panel ── */
function SendPanel({ targetCount }: { targetCount: number }) {
  const lang = useAppStore((s) => s.lang);
  const { toast } = useAdminToast();
  const queryClient = useQueryClient();
  const [confirmSend, setConfirmSend] = useState(false);

  const testSend = useMutation({
    mutationFn: () => adminFetch("/admin/weekly-report/send-test", { method: "POST" }),
    onSuccess: (d: unknown) => {
      toast(`${t(lang, "admin_wr_send_success")} → ${(d as { sent_to: string }).sent_to}`, "success");
    },
    onError: () => toast(t(lang, "admin_wr_send_fail"), "error"),
  });

  const fullSend = useMutation({
    mutationFn: () => adminFetch("/admin/weekly-report/send", { method: "POST" }),
    onSuccess: (d: unknown) => {
      const res = d as { sent: number; failed: number };
      toast(`${t(lang, "admin_wr_send_success")} — ${res.sent} sent, ${res.failed} failed`, "success");
      setConfirmSend(false);
      queryClient.invalidateQueries({ queryKey: ["admin-weekly-report-history"] });
    },
    onError: () => {
      toast(t(lang, "admin_wr_send_fail"), "error");
      setConfirmSend(false);
    },
  });

  return (
    <div className="rounded-xl border border-border bg-card p-4 space-y-4">
      <h3 className="text-sm font-semibold flex items-center gap-2">
        <Send className="h-4 w-4 text-primary" />
        {lang === "ko" ? "발송 컨트롤" : "Send Control"}
      </h3>

      {/* Target count */}
      <div className="rounded-lg bg-secondary/50 p-3 text-center">
        <p className="text-xs text-muted-foreground">{t(lang, "admin_wr_send_target")}</p>
        <p className="text-2xl font-bold tabular-nums mt-1">{targetCount}</p>
        <p className="text-[10px] text-muted-foreground">{lang === "ko" ? "명" : "users"}</p>
      </div>

      {/* Test send */}
      <button
        onClick={() => testSend.mutate()}
        disabled={testSend.isPending}
        className="w-full flex items-center justify-center gap-2 rounded-lg border border-border px-3 py-2 text-sm hover:bg-secondary transition-colors disabled:opacity-50"
      >
        {testSend.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <TestTube className="h-4 w-4" />}
        {t(lang, "admin_wr_send_test")}
      </button>

      {/* Full send */}
      {!confirmSend ? (
        <button
          onClick={() => setConfirmSend(true)}
          className="w-full flex items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Mail className="h-4 w-4" />
          {t(lang, "admin_wr_send_all")}
        </button>
      ) : (
        <div className="space-y-2">
          <p className="text-xs text-center text-orange-400">{t(lang, "admin_wr_send_confirm")}</p>
          <div className="flex gap-2">
            <button
              onClick={() => setConfirmSend(false)}
              className="flex-1 rounded-lg border border-border px-3 py-2 text-sm hover:bg-secondary transition-colors"
            >
              {t(lang, "admin_cancel")}
            </button>
            <button
              onClick={() => fullSend.mutate()}
              disabled={fullSend.isPending}
              className="flex-1 rounded-lg bg-red-500 px-3 py-2 text-sm font-medium text-white hover:bg-red-600 transition-colors disabled:opacity-50"
            >
              {fullSend.isPending ? <Loader2 className="h-4 w-4 animate-spin mx-auto" /> : (lang === "ko" ? "확인" : "Confirm")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Main Page ── */
export default function AdminWeeklyReportPage() {
  const lang = useAppStore((s) => s.lang);
  const [activeTab, setActiveTab] = useState("preview");
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery<DraftData>({
    queryKey: ["admin-weekly-report-draft"],
    queryFn: () => adminFetch<DraftData>("/admin/weekly-report/draft"),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-center py-20 text-muted-foreground">
        {lang === "ko" ? "데이터를 불러올 수 없습니다." : "Failed to load data."}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">{t(lang, "admin_weekly_report")}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {data.week} · {lang === "ko" ? "주간 리포트를 관리하고 발송합니다" : "Manage and send weekly reports"}
        </p>
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Main content */}
        <div className="flex-1 min-w-0">
          <TabBar
            tabs={[
              { key: "preview", label: t(lang, "admin_wr_tab_preview"), icon: Eye },
              { key: "edit", label: t(lang, "admin_wr_tab_edit"), icon: Edit3 },
              { key: "history", label: t(lang, "admin_wr_tab_history"), icon: Clock },
            ]}
            activeTab={activeTab}
            onChange={setActiveTab}
          />

          {activeTab === "preview" && <ReportPreview data={data} />}
          {activeTab === "edit" && (
            <ReportEditor
              data={data}
              onSaved={() => queryClient.invalidateQueries({ queryKey: ["admin-weekly-report-draft"] })}
            />
          )}
          {activeTab === "history" && <ReportHistory />}
        </div>

        {/* Right panel */}
        <div className="lg:w-64 shrink-0">
          <div className="lg:sticky lg:top-4">
            <SendPanel targetCount={data.target_count} />
          </div>
        </div>
      </div>
    </div>
  );
}
