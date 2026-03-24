"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { adminFetch } from "@/lib/admin-utils";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useAdminToast } from "@/components/ui/admin-toast";
import { TabBar } from "@/components/admin/TabBar";
import {
  Save, Send, ChevronDown, ChevronRight, Loader2,
  Smartphone, Monitor, AlertTriangle, FileText,
  Mail, Clock, CheckCircle, XCircle,
} from "lucide-react";

/* ── 변수 그룹 정의 ── */
interface FieldDef {
  key: string;
  label: string;
  type: "input" | "textarea";
  rows?: number;
  maxLength?: number;
}

interface SectionDef {
  id: string;
  labelKo: string;
  labelEn: string;
  fields: FieldDef[];
}

const SECTIONS: SectionDef[] = [
  {
    id: "basic",
    labelKo: "기본 정보",
    labelEn: "Basic Info",
    fields: [
      { key: "vol_number", label: "Vol Number", type: "input" },
      { key: "issue_date", label: "Issue Date", type: "input" },
      { key: "issue_date_short", label: "Date Short", type: "input" },
      { key: "issue_datetime", label: "Date Time", type: "input" },
      { key: "issue_label", label: "Issue Label", type: "input" },
      { key: "issue_label_long", label: "Label Long", type: "input" },
    ],
  },
  {
    id: "preheader",
    labelKo: "프리헤더",
    labelEn: "Preheader",
    fields: [
      { key: "preheader_text", label: "Preheader Text", type: "input", maxLength: 120 },
    ],
  },
  {
    id: "hero",
    labelKo: "히어로",
    labelEn: "Hero",
    fields: [
      { key: "hero_image_url", label: "Hero Image URL", type: "input" },
      { key: "hero_headline_html", label: "Hero Headline (HTML)", type: "textarea", rows: 3 },
      { key: "crisis_countries_count", label: "Crisis Countries", type: "input" },
      { key: "crisis_prev", label: "Crisis Prev", type: "input" },
      { key: "crisis_current", label: "Crisis Current", type: "input" },
      { key: "crisis_trend", label: "Crisis Trend", type: "input" },
      { key: "events_24h", label: "Events 24h", type: "input" },
      { key: "events_7d", label: "Events 7d", type: "input" },
      { key: "key_stats_line", label: "Key Stats (HTML)", type: "textarea", rows: 2 },
    ],
  },
  {
    id: "nav",
    labelKo: "내비",
    labelEn: "Navigation",
    fields: [
      { key: "deep_dive_nav_label", label: "Deep Dive Nav", type: "input" },
    ],
  },
  {
    id: "stats",
    labelKo: "통계",
    labelEn: "Statistics",
    fields: [
      { key: "total_conflicts", label: "Total Conflicts", type: "input" },
      { key: "urgent_count", label: "Urgent Count", type: "input" },
      { key: "active_issues_count", label: "Active Issues", type: "input" },
    ],
  },
  {
    id: "brief",
    labelKo: "Today's Brief",
    labelEn: "Today's Brief",
    fields: [
      { key: "todays_brief_items_html", label: "Brief Items (HTML)", type: "textarea", rows: 10 },
    ],
  },
  {
    id: "tension",
    labelKo: "긴장도 TOP 10",
    labelEn: "Tension Index",
    fields: [
      { key: "tension_table_html", label: "Tension Table (HTML)", type: "textarea", rows: 12 },
      { key: "tension_warning_html", label: "Tension Warning (HTML)", type: "textarea", rows: 3 },
    ],
  },
  {
    id: "conflict",
    labelKo: "전쟁·분쟁",
    labelEn: "Conflicts",
    fields: [
      { key: "conflict_stories_html", label: "Conflict Stories (HTML)", type: "textarea", rows: 12 },
    ],
  },
  {
    id: "energy",
    labelKo: "에너지",
    labelEn: "Energy",
    fields: [
      { key: "energy_section_intro_html", label: "Energy Intro (HTML)", type: "textarea", rows: 3 },
      { key: "energy_section_html", label: "Energy Section (HTML)", type: "textarea", rows: 12 },
    ],
  },
  {
    id: "deepdive",
    labelKo: "딥다이브",
    labelEn: "Deep Dive",
    fields: [
      { key: "deep_dive_title", label: "Deep Dive Title", type: "input" },
      { key: "deep_dive_section_html", label: "Deep Dive (HTML)", type: "textarea", rows: 12 },
    ],
  },
  {
    id: "country",
    labelKo: "국가 섹션",
    labelEn: "Country",
    fields: [
      { key: "country_name", label: "Country Name", type: "input" },
      { key: "country_code", label: "Country Code", type: "input" },
      { key: "country_rank", label: "Rank", type: "input" },
      { key: "tension_level", label: "Tension Level", type: "input" },
      { key: "tension_score", label: "Tension Score", type: "input" },
      { key: "tension_level_text", label: "Level Text", type: "input" },
      { key: "tension_change", label: "Change", type: "input" },
      { key: "prev_tension", label: "Prev Tension", type: "input" },
      { key: "streak_text", label: "Streak Text", type: "input" },
      { key: "country_summary", label: "Country Summary", type: "textarea", rows: 3 },
      { key: "country_issues_html", label: "Country Issues (HTML)", type: "textarea", rows: 8 },
      { key: "country_impact_html", label: "Country Impact (HTML)", type: "textarea", rows: 8 },
    ],
  },
  {
    id: "travel",
    labelKo: "여행경보",
    labelEn: "Travel Advisory",
    fields: [
      { key: "travel_advisory_intro_html", label: "Travel Intro (HTML)", type: "textarea", rows: 3 },
      { key: "travel_advisory_html", label: "Travel Advisory (HTML)", type: "textarea", rows: 8 },
      { key: "did_you_know_html", label: "Did You Know (HTML)", type: "textarea", rows: 4 },
    ],
  },
  {
    id: "numbers",
    labelKo: "숫자·캘린더",
    labelEn: "Numbers & Calendar",
    fields: [
      { key: "numbers_section_html", label: "Numbers Section (HTML)", type: "textarea", rows: 10 },
      { key: "calendar_html", label: "Calendar (HTML)", type: "textarea", rows: 10 },
    ],
  },
  {
    id: "editor",
    labelKo: "에디터 노트",
    labelEn: "Editor's Note",
    fields: [
      { key: "editors_note_html", label: "Editor's Note (HTML)", type: "textarea", rows: 6 },
      { key: "next_week_items_html", label: "Next Week (HTML)", type: "textarea", rows: 6 },
    ],
  },
  {
    id: "share",
    labelKo: "공유·CTA",
    labelEn: "Share & CTA",
    fields: [
      { key: "share_headline", label: "Share Headline", type: "input" },
      { key: "share_subtext", label: "Share Subtext", type: "input" },
      { key: "mailto_subject", label: "Mailto Subject", type: "input" },
      { key: "mailto_body", label: "Mailto Body", type: "textarea", rows: 3 },
      { key: "pro_cta_headline_html", label: "Pro CTA Headline (HTML)", type: "textarea", rows: 3 },
      { key: "pro_cta_subtext", label: "Pro CTA Subtext", type: "input" },
    ],
  },
  {
    id: "system",
    labelKo: "시스템",
    labelEn: "System",
    fields: [
      { key: "unsubscribe_url", label: "Unsubscribe URL", type: "input" },
      { key: "next_vol_number", label: "Next Vol Number", type: "input" },
    ],
  },
];

/* ── 접이식 섹션 컴포넌트 ── */
function CollapsibleSection({
  section,
  lang,
  data,
  onChange,
  defaultOpen,
}: {
  section: SectionDef;
  lang: "ko" | "en";
  data: Record<string, any>;
  onChange: (key: string, value: string) => void;
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const label = lang === "ko" ? section.labelKo : section.labelEn;

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-4 py-2.5 bg-secondary/30 hover:bg-secondary/50 transition-colors text-left"
      >
        {open ? <ChevronDown className="h-4 w-4 shrink-0" /> : <ChevronRight className="h-4 w-4 shrink-0" />}
        <span className="text-sm font-medium">{label}</span>
        <span className="text-[10px] text-muted-foreground ml-auto">{section.fields.length}</span>
      </button>
      {open && (
        <div className="p-4 space-y-3">
          {section.fields.map((field) => (
            <div key={field.key}>
              <label className="block text-xs text-muted-foreground mb-1">
                {field.label}
                {field.maxLength && (
                  <span className={cn(
                    "ml-2",
                    (data[field.key]?.length || 0) > field.maxLength ? "text-red-400" : "text-muted-foreground/60",
                  )}>
                    {data[field.key]?.length || 0}/{field.maxLength}
                  </span>
                )}
              </label>
              {field.type === "input" ? (
                <input
                  type="text"
                  value={data[field.key] ?? ""}
                  onChange={(e) => onChange(field.key, e.target.value)}
                  className="w-full px-3 py-1.5 text-sm bg-background border border-border rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                />
              ) : (
                <textarea
                  value={data[field.key] ?? ""}
                  onChange={(e) => onChange(field.key, e.target.value)}
                  rows={field.rows || 4}
                  className="w-full px-3 py-1.5 text-xs font-mono bg-background border border-border rounded-md focus:outline-none focus:ring-1 focus:ring-primary resize-y"
                />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── 프리뷰 패널 ── */
function PreviewPanel({
  html,
  sizeKb,
  unresolved,
  loading,
  lang,
}: {
  html: string;
  sizeKb: number;
  unresolved: string[];
  loading: boolean;
  lang: "ko" | "en";
}) {
  const [mobileView, setMobileView] = useState(false);
  const maxKb = 102;
  const pct = Math.min((sizeKb / maxKb) * 100, 100);
  const isOver = sizeKb > maxKb;

  return (
    <div className="flex flex-col h-full">
      {/* 상단 메타 */}
      <div className="flex items-center gap-3 pb-3 border-b border-border flex-nowrap">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <FileText className="h-3.5 w-3.5 shrink-0" />
            <span className={cn(isOver && "text-red-400 font-medium")}>
              {sizeKb}KB / {maxKb}KB
            </span>
            {loading && <Loader2 className="h-3 w-3 animate-spin" />}
          </div>
          <div className="mt-1 h-1.5 bg-secondary rounded-full overflow-hidden">
            <div
              className={cn("h-full rounded-full transition-all", isOver ? "bg-red-500" : "bg-primary")}
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
        {unresolved.length > 0 && (
          <div className="flex items-center gap-1 text-amber-400 text-[10px] shrink-0" title={unresolved.join(", ")}>
            <AlertTriangle className="h-3 w-3" />
            {unresolved.length}
          </div>
        )}
        <div className="flex gap-1 shrink-0">
          <button
            onClick={() => setMobileView(false)}
            className={cn(
              "p-1.5 rounded",
              !mobileView ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground",
            )}
          >
            <Monitor className="h-4 w-4" />
          </button>
          <button
            onClick={() => setMobileView(true)}
            className={cn(
              "p-1.5 rounded",
              mobileView ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground",
            )}
          >
            <Smartphone className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* iframe */}
      <div className="flex-1 mt-3 flex justify-center overflow-auto bg-secondary/20 rounded-lg">
        {html ? (
          <iframe
            srcDoc={html}
            className={cn(
              "border-0 bg-white rounded shadow-lg transition-all",
              mobileView ? "w-[390px]" : "w-full",
            )}
            style={{ minHeight: 600, height: "100%" }}
            sandbox="allow-same-origin"
            title="Newsletter Preview"
          />
        ) : (
          <div className="flex items-center justify-center h-96 text-muted-foreground text-sm">
            {lang === "ko" ? "데이터를 입력하면 미리보기가 표시됩니다" : "Enter data to see preview"}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── 메인 페이지 ── */
export default function AdminNewsletterPage() {
  const { lang } = useAppStore();
  const { toast } = useAdminToast();
  const [editLang, setEditLang] = useState<"kr" | "us">("kr");
  const [vol, setVol] = useState(1);
  const [data, setData] = useState<Record<string, any>>({});
  const [previewHtml, setPreviewHtml] = useState("");
  const [sizeKb, setSizeKb] = useState(0);
  const [unresolved, setUnresolved] = useState<string[]>([]);
  const [renderLoading, setRenderLoading] = useState(false);
  const [mobileTab, setMobileTab] = useState<"edit" | "preview">("edit");
  const [confirmSend, setConfirmSend] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  // 초안 로드
  const { data: draftData, isLoading: draftLoading } = useQuery({
    queryKey: ["newsletter-draft", vol, editLang],
    queryFn: () => adminFetch<Record<string, any>>(`/admin/newsletter/draft?vol=${vol}&lang=${editLang}`),
    refetchOnWindowFocus: false,
  });

  // draftData 변경 시 data에 반영
  useEffect(() => {
    if (draftData) setData(draftData);
  }, [draftData]);

  // 렌더링 함수
  const doRender = useCallback(async (renderData: Record<string, any>) => {
    setRenderLoading(true);
    try {
      const res = await adminFetch<{ html: string; size_kb: number; unresolved: string[] }>(
        "/admin/newsletter/render",
        { method: "POST", body: { lang: editLang, data: renderData } },
      );
      setPreviewHtml(res.html);
      setSizeKb(res.size_kb);
      setUnresolved(res.unresolved);
    } catch (err) {
      console.error("[newsletter render]", err);
    } finally {
      setRenderLoading(false);
    }
  }, [editLang]);

  // 디바운스 렌더
  useEffect(() => {
    if (Object.keys(data).length === 0) return;
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doRender(data), 500);
    return () => clearTimeout(debounceRef.current);
  }, [data, doRender]);

  // 필드 변경
  const handleChange = useCallback((key: string, value: string) => {
    setData((prev) => ({ ...prev, [key]: value }));
  }, []);

  // 저장
  const saveMutation = useMutation({
    mutationFn: () =>
      adminFetch("/admin/newsletter/draft", {
        method: "PUT",
        body: { vol, lang: editLang, data },
      }),
    onSuccess: () => toast(lang === "ko" ? "초안 저장됨" : "Draft saved", "success"),
    onError: () => toast(lang === "ko" ? "저장 실패" : "Save failed", "error"),
  });

  // 테스트 발송
  const sendTestMutation = useMutation({
    mutationFn: () =>
      adminFetch<{ sent_to: string }>("/admin/newsletter/send-test", {
        method: "POST",
        body: { lang: editLang, data },
      }),
    onSuccess: (res) => {
      const r = res as { sent_to: string };
      toast(lang === "ko" ? `테스트 발송 → ${r.sent_to}` : `Test sent → ${r.sent_to}`, "success");
    },
    onError: () => toast(lang === "ko" ? "발송 실패" : "Send failed", "error"),
  });

  // 전체 발송
  const sendAllMutation = useMutation({
    mutationFn: () =>
      adminFetch<{ sent: number; failed: number }>("/admin/newsletter/send", {
        method: "POST",
        body: { vol, lang: editLang, data },
      }),
    onSuccess: (res) => {
      const r = res as { sent: number; failed: number };
      toast(lang === "ko" ? `발송 완료 — ${r.sent}명 성공, ${r.failed}명 실패` : `Sent — ${r.sent} ok, ${r.failed} failed`, "success");
      setConfirmSend(false);
    },
    onError: () => {
      toast(lang === "ko" ? "발송 실패" : "Send failed", "error");
      setConfirmSend(false);
    },
  });

  // 발송 기록
  const { data: historyData } = useQuery({
    queryKey: ["newsletter-history"],
    queryFn: () => adminFetch<Array<{ id: number; date: string; subject: string; sent: number; failed: number; status: string }>>("/admin/newsletter/history"),
  });

  const langTabs = [
    { key: "kr", label: "KR 한국어" },
    { key: "us", label: "EN English" },
  ];

  const mobileTabs = [
    { key: "edit", label: lang === "ko" ? "편집" : "Edit" },
    { key: "preview", label: lang === "ko" ? "미리보기" : "Preview" },
  ];

  return (
    <div className="space-y-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between flex-nowrap">
        <div>
          <h1 className="text-lg font-bold">{t(lang, "admin_newsletter")}</h1>
          <p className="text-xs text-muted-foreground">
            Vol.{vol} · {data.issue_date || "—"}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <label className="text-xs text-muted-foreground">Vol</label>
          <input
            type="number"
            min={1}
            value={vol}
            onChange={(e) => setVol(Number(e.target.value) || 1)}
            className="w-14 px-2 py-1 text-xs bg-background border border-border rounded"
          />
        </div>
      </div>

      {/* 언어 탭 */}
      <TabBar
        tabs={langTabs}
        activeTab={editLang}
        onChange={(k) => setEditLang(k as "kr" | "us")}
      />

      {/* 모바일 탭 (lg 이하) */}
      <div className="lg:hidden">
        <TabBar tabs={mobileTabs} activeTab={mobileTab} onChange={(k) => setMobileTab(k as "edit" | "preview")} />
      </div>

      {draftLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      ) : (
        <div className="flex flex-col lg:flex-row gap-6">
          {/* 에디터 패널 */}
          <div className={cn(
            "w-full lg:w-1/2 xl:w-5/12 space-y-2",
            mobileTab !== "edit" && "hidden lg:block",
          )}>
            {SECTIONS.map((section, i) => (
              <CollapsibleSection
                key={section.id}
                section={section}
                lang={lang}
                data={data}
                onChange={handleChange}
                defaultOpen={i === 0}
              />
            ))}

            {/* 액션 버튼 */}
            <div className="flex gap-3 pt-4 pb-8 sticky bottom-0 bg-background/80 backdrop-blur-sm">
              <button
                onClick={() => saveMutation.mutate()}
                disabled={saveMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
              >
                {saveMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                {lang === "ko" ? "저장" : "Save"}
              </button>
              <button
                onClick={() => sendTestMutation.mutate()}
                disabled={sendTestMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-secondary text-foreground rounded-lg text-sm font-medium hover:bg-secondary/80 disabled:opacity-50"
              >
                {sendTestMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                {lang === "ko" ? "테스트 발송" : "Send Test"}
              </button>
              {!confirmSend ? (
                <button
                  onClick={() => setConfirmSend(true)}
                  className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700"
                >
                  <Mail className="h-4 w-4" />
                  {lang === "ko" ? "전체 발송" : "Send All"}
                </button>
              ) : (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => sendAllMutation.mutate()}
                    disabled={sendAllMutation.isPending}
                    className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-50 animate-pulse"
                  >
                    {sendAllMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
                    {lang === "ko" ? "정말 발송" : "Confirm"}
                  </button>
                  <button
                    onClick={() => setConfirmSend(false)}
                    className="px-3 py-2 text-xs text-muted-foreground hover:text-foreground"
                  >
                    {lang === "ko" ? "취소" : "Cancel"}
                  </button>
                </div>
              )}
            </div>

            {/* 발송 기록 */}
            {historyData && historyData.length > 0 && (
              <div className="border border-border rounded-lg p-4 space-y-3">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  {lang === "ko" ? "발송 기록" : "Send History"}
                </h3>
                <div className="space-y-2">
                  {historyData.map((h) => (
                    <div key={h.id} className="flex items-center justify-between text-xs py-1.5 border-b border-border/40 last:border-0">
                      <div className="flex items-center gap-2">
                        {h.status === "completed" ? (
                          <CheckCircle className="h-3.5 w-3.5 text-green-400" />
                        ) : (
                          <XCircle className="h-3.5 w-3.5 text-red-400" />
                        )}
                        <span className="text-muted-foreground">{h.subject}</span>
                      </div>
                      <div className="flex items-center gap-3 text-muted-foreground">
                        <span>{h.sent}{lang === "ko" ? "명" : " sent"}</span>
                        {h.failed > 0 && <span className="text-red-400">{h.failed}{lang === "ko" ? " 실패" : " failed"}</span>}
                        <span>{h.date ? new Date(h.date).toLocaleDateString(lang === "ko" ? "ko-KR" : "en-US") : "—"}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* 프리뷰 패널 */}
          <div className={cn(
            "w-full lg:w-1/2 xl:w-7/12 lg:sticky lg:top-0 lg:h-[calc(100vh-8rem)]",
            mobileTab !== "preview" && "hidden lg:block",
          )}>
            <PreviewPanel
              html={previewHtml}
              sizeKb={sizeKb}
              unresolved={unresolved}
              loading={renderLoading}
              lang={lang}
            />
          </div>
        </div>
      )}
    </div>
  );
}
