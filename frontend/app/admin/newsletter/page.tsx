"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
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
  ChevronsUpDown, Search, Copy, Check, Hash, Eye,
  Download, Upload, Filter, ExternalLink,
} from "lucide-react";

/* ── 변수 그룹 정의 ── */
interface FieldDef {
  key: string;
  label: string;
  type: "input" | "textarea";
  rows?: number;
  maxLength?: number;
  placeholder?: string;
  hint?: string;
}

interface SectionDef {
  id: string;
  labelKo: string;
  labelEn: string;
  icon?: string;
  fields: FieldDef[];
}

const SECTIONS: SectionDef[] = [
  {
    id: "basic",
    labelKo: "기본 정보",
    labelEn: "Basic Info",
    icon: "📋",
    fields: [
      { key: "vol_number", label: "Vol Number", type: "input", placeholder: "1", hint: "호수 번호" },
      { key: "issue_date", label: "Issue Date", type: "input", placeholder: "2026년 3월 24일", hint: "전체 날짜 표시" },
      { key: "issue_date_short", label: "Date Short", type: "input", placeholder: "2026.3.24", hint: "짧은 날짜" },
      { key: "issue_datetime", label: "Date Time", type: "input", placeholder: "2026-03-24T09:00:00+09:00", hint: "ISO 8601" },
      { key: "issue_label", label: "Issue Label", type: "input", placeholder: "Vol.1", hint: "짧은 라벨" },
      { key: "issue_label_long", label: "Label Long", type: "input", placeholder: "Vol.1 — 2026.3.24", hint: "전체 라벨" },
    ],
  },
  {
    id: "preheader",
    labelKo: "프리헤더",
    labelEn: "Preheader",
    icon: "👁",
    fields: [
      { key: "preheader_text", label: "Preheader Text", type: "input", maxLength: 120, placeholder: "받은편지함에 보이는 미리보기 텍스트...", hint: "Gmail 미리보기, 120자 이내 권장" },
    ],
  },
  {
    id: "hero",
    labelKo: "히어로",
    labelEn: "Hero",
    icon: "🎯",
    fields: [
      { key: "hero_image_url", label: "Hero Image URL", type: "input", placeholder: "https://...", hint: "1200x630 권장" },
      { key: "hero_headline_html", label: "Hero Headline (HTML)", type: "textarea", rows: 3, hint: "메인 타이틀, HTML 가능" },
      { key: "crisis_countries_count", label: "Crisis Countries", type: "input", placeholder: "42", hint: "위기 국가 수" },
      { key: "crisis_prev", label: "Crisis Prev", type: "input", placeholder: "38", hint: "전주 위기 국가 수" },
      { key: "crisis_current", label: "Crisis Current", type: "input", placeholder: "42", hint: "이번주 위기 국가 수" },
      { key: "crisis_trend", label: "Crisis Trend", type: "input", placeholder: "↑ 4", hint: "↑↓ + 숫자" },
      { key: "events_24h", label: "Events 24h", type: "input", placeholder: "2,048", hint: "24시간 이벤트 수" },
      { key: "events_7d", label: "Events 7d", type: "input", placeholder: "12,340", hint: "7일 이벤트 수" },
      { key: "key_stats_line", label: "Key Stats (HTML)", type: "textarea", rows: 2, hint: "히어로 하단 핵심 통계 HTML" },
    ],
  },
  {
    id: "nav",
    labelKo: "내비",
    labelEn: "Navigation",
    icon: "🧭",
    fields: [
      { key: "deep_dive_nav_label", label: "Deep Dive Nav", type: "input", placeholder: "호르무즈 해협", hint: "딥다이브 네비 라벨" },
    ],
  },
  {
    id: "stats",
    labelKo: "통계",
    labelEn: "Statistics",
    icon: "📊",
    fields: [
      { key: "total_conflicts", label: "Total Conflicts", type: "input", placeholder: "56", hint: "총 분쟁 수" },
      { key: "urgent_count", label: "Urgent Count", type: "input", placeholder: "12", hint: "긴급 이슈 수" },
      { key: "active_issues_count", label: "Active Issues", type: "input", placeholder: "948", hint: "진행 중 이슈 수" },
    ],
  },
  {
    id: "brief",
    labelKo: "Today's Brief",
    labelEn: "Today's Brief",
    icon: "📰",
    fields: [
      { key: "todays_brief_items_html", label: "Brief Items (HTML)", type: "textarea", rows: 10, hint: "오늘의 브리프 항목 HTML 블록" },
    ],
  },
  {
    id: "tension",
    labelKo: "긴장도 TOP 10",
    labelEn: "Tension Index",
    icon: "🔥",
    fields: [
      { key: "tension_table_html", label: "Tension Table (HTML)", type: "textarea", rows: 12, hint: "긴장도 순위 테이블 HTML" },
      { key: "tension_warning_html", label: "Tension Warning (HTML)", type: "textarea", rows: 3, hint: "경고 메시지 HTML" },
    ],
  },
  {
    id: "conflict",
    labelKo: "전쟁·분쟁",
    labelEn: "Conflicts",
    icon: "⚔",
    fields: [
      { key: "conflict_stories_html", label: "Conflict Stories (HTML)", type: "textarea", rows: 12, hint: "분쟁 스토리 HTML 블록" },
    ],
  },
  {
    id: "energy",
    labelKo: "에너지",
    labelEn: "Energy",
    icon: "⛽",
    fields: [
      { key: "energy_section_intro_html", label: "Energy Intro (HTML)", type: "textarea", rows: 3, hint: "에너지 섹션 도입부" },
      { key: "energy_section_html", label: "Energy Section (HTML)", type: "textarea", rows: 12, hint: "에너지 본문 HTML 블록" },
    ],
  },
  {
    id: "deepdive",
    labelKo: "딥다이브",
    labelEn: "Deep Dive",
    icon: "🔬",
    fields: [
      { key: "deep_dive_title", label: "Deep Dive Title", type: "input", placeholder: "호르무즈 해협 위기", hint: "딥다이브 제목" },
      { key: "deep_dive_section_html", label: "Deep Dive (HTML)", type: "textarea", rows: 12, hint: "딥다이브 본문 HTML 블록" },
    ],
  },
  {
    id: "country",
    labelKo: "국가 섹션",
    labelEn: "Country",
    icon: "🌏",
    fields: [
      { key: "country_name", label: "Country Name", type: "input", placeholder: "한국 / South Korea", hint: "국가명" },
      { key: "country_code", label: "Country Code", type: "input", placeholder: "KR", hint: "ISO 2자리 코드" },
      { key: "country_rank", label: "Rank", type: "input", placeholder: "8", hint: "긴장도 순위" },
      { key: "tension_level", label: "Tension Level", type: "input", placeholder: "4", hint: "1~5 레벨" },
      { key: "tension_score", label: "Tension Score", type: "input", placeholder: "96.8", hint: "긴장도 점수" },
      { key: "tension_level_text", label: "Level Text", type: "input", placeholder: "LEVEL 4", hint: "레벨 텍스트" },
      { key: "tension_change", label: "Change", type: "input", placeholder: "↑24%", hint: "변동 표시" },
      { key: "prev_tension", label: "Prev Tension", type: "input", placeholder: "78.2", hint: "전주 점수" },
      { key: "streak_text", label: "Streak Text", type: "input", placeholder: "3주 연속 상승", hint: "추세 텍스트" },
      { key: "country_summary", label: "Country Summary", type: "textarea", rows: 3, hint: "국가 요약 설명" },
      { key: "country_issues_html", label: "Country Issues (HTML)", type: "textarea", rows: 8, hint: "국가 이슈 상세 HTML" },
      { key: "country_impact_html", label: "Country Impact (HTML)", type: "textarea", rows: 8, hint: "국가 영향 분석 HTML" },
    ],
  },
  {
    id: "travel",
    labelKo: "여행경보",
    labelEn: "Travel Advisory",
    icon: "✈",
    fields: [
      { key: "travel_advisory_intro_html", label: "Travel Intro (HTML)", type: "textarea", rows: 3, hint: "여행경보 도입부" },
      { key: "travel_advisory_html", label: "Travel Advisory (HTML)", type: "textarea", rows: 8, hint: "여행경보 본문 HTML" },
      { key: "did_you_know_html", label: "Did You Know (HTML)", type: "textarea", rows: 4, hint: "알고 계셨나요? HTML" },
    ],
  },
  {
    id: "numbers",
    labelKo: "숫자·캘린더",
    labelEn: "Numbers & Calendar",
    icon: "🔢",
    fields: [
      { key: "numbers_section_html", label: "Numbers Section (HTML)", type: "textarea", rows: 10, hint: "이번주 숫자 HTML" },
      { key: "calendar_html", label: "Calendar (HTML)", type: "textarea", rows: 10, hint: "다음주 캘린더 HTML" },
    ],
  },
  {
    id: "editor",
    labelKo: "에디터 노트",
    labelEn: "Editor's Note",
    icon: "✏",
    fields: [
      { key: "editors_note_html", label: "Editor's Note (HTML)", type: "textarea", rows: 6, hint: "에디터 인사말 HTML" },
      { key: "next_week_items_html", label: "Next Week (HTML)", type: "textarea", rows: 6, hint: "다음주 예고 HTML" },
    ],
  },
  {
    id: "share",
    labelKo: "공유·CTA",
    labelEn: "Share & CTA",
    icon: "📤",
    fields: [
      { key: "share_headline", label: "Share Headline", type: "input", placeholder: "친구에게 공유", hint: "공유 제목" },
      { key: "share_subtext", label: "Share Subtext", type: "input", placeholder: "이 뉴스레터가 도움이 됐다면...", hint: "공유 부제" },
      { key: "mailto_subject", label: "Mailto Subject", type: "input", placeholder: "WeWantPeace 뉴스레터 추천", hint: "공유 이메일 제목" },
      { key: "mailto_body", label: "Mailto Body", type: "textarea", rows: 3, hint: "공유 이메일 본문" },
      { key: "pro_cta_headline_html", label: "Pro CTA Headline (HTML)", type: "textarea", rows: 3, hint: "PRO 업그레이드 CTA HTML" },
      { key: "pro_cta_subtext", label: "Pro CTA Subtext", type: "input", placeholder: "더 깊은 분석...", hint: "PRO CTA 부제" },
    ],
  },
  {
    id: "system",
    labelKo: "시스템",
    labelEn: "System",
    icon: "⚙",
    fields: [
      { key: "unsubscribe_url", label: "Unsubscribe URL", type: "input", placeholder: "https://...", hint: "수신거부 URL" },
      { key: "next_vol_number", label: "Next Vol Number", type: "input", placeholder: "2", hint: "다음호 번호" },
    ],
  },
];

/* ── 복사 버튼 ── */
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <button
      onClick={handleCopy}
      className="p-1 rounded hover:bg-secondary/80 text-muted-foreground hover:text-foreground transition-colors"
      title="Copy"
    >
      {copied ? <Check className="h-3 w-3 text-green-400" /> : <Copy className="h-3 w-3" />}
    </button>
  );
}

/* ── 필드 에디터 컴포넌트 ── */
function FieldEditor({
  field,
  data,
  onChange,
}: {
  field: FieldDef;
  data: Record<string, any>;
  onChange: (key: string, value: string) => void;
}) {
  const [showPreview, setShowPreview] = useState(false);
  const value = data[field.key] ?? "";
  const strVal = String(value);
  const isHtml = field.label.includes("HTML");
  const lineCount = strVal.split("\n").length;
  const isEmpty = strVal.trim() === "";

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
          {isHtml && <Hash className="h-3 w-3 text-amber-400/60" />}
          <span>{field.label}</span>
          {field.maxLength && (
            <span className={cn(
              "ml-1 tabular-nums",
              strVal.length > field.maxLength ? "text-red-400 font-medium" : "text-muted-foreground/60",
            )}>
              {strVal.length}/{field.maxLength}
            </span>
          )}
          {field.type === "textarea" && !isEmpty && (
            <span className="text-[10px] text-muted-foreground/40 tabular-nums">{lineCount}L · {strVal.length}ch</span>
          )}
          {field.hint && (
            <span className="text-[10px] text-muted-foreground/40 ml-1 hidden sm:inline">{field.hint}</span>
          )}
        </label>
        <div className="flex items-center gap-1">
          {isHtml && strVal.length > 0 && (
            <>
              <button
                onClick={() => setShowPreview(!showPreview)}
                className="p-1 rounded hover:bg-secondary/80 text-muted-foreground hover:text-foreground transition-colors"
                title="Preview HTML"
              >
                <Eye className="h-3 w-3" />
              </button>
              <CopyButton text={strVal} />
            </>
          )}
        </div>
      </div>
      {field.type === "input" ? (
        <input
          type="text"
          value={strVal}
          onChange={(e) => onChange(field.key, e.target.value)}
          placeholder={field.placeholder}
          className={cn(
            "w-full px-3 py-1.5 text-sm bg-background border border-border rounded-md focus:outline-none focus:ring-1 focus:ring-primary placeholder:text-muted-foreground/30",
            isEmpty && "border-dashed border-muted-foreground/30",
          )}
        />
      ) : (
        <>
          <textarea
            value={strVal}
            onChange={(e) => onChange(field.key, e.target.value)}
            rows={field.rows || 4}
            placeholder={field.placeholder}
            className={cn(
              "w-full px-3 py-1.5 text-xs font-mono bg-background border border-border rounded-md focus:outline-none focus:ring-1 focus:ring-primary resize-y placeholder:text-muted-foreground/30",
              isHtml && "bg-slate-950/30",
              isEmpty && "border-dashed border-muted-foreground/30",
            )}
          />
          {showPreview && isHtml && strVal.length > 0 && (
            <div className="mt-1 p-3 bg-white text-black text-xs rounded border border-border overflow-auto max-h-48">
              <div dangerouslySetInnerHTML={{ __html: strVal }} />
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ── 접이식 섹션 컴포넌트 ── */
function CollapsibleSection({
  section,
  lang,
  data,
  onChange,
  open,
  onToggle,
  searchQuery,
  showEmptyOnly,
}: {
  section: SectionDef;
  lang: "ko" | "en";
  data: Record<string, any>;
  onChange: (key: string, value: string) => void;
  open: boolean;
  onToggle: () => void;
  searchQuery: string;
  showEmptyOnly: boolean;
}) {
  const label = lang === "ko" ? section.labelKo : section.labelEn;
  const filledCount = section.fields.filter((f) => {
    const v = data[f.key];
    return v !== undefined && v !== null && String(v).trim() !== "";
  }).length;
  const totalCount = section.fields.length;
  const allFilled = filledCount === totalCount;

  // 필터링: 검색 + 빈 필드만 보기
  let visibleFields = section.fields;
  if (searchQuery) {
    visibleFields = visibleFields.filter((f) =>
      f.key.toLowerCase().includes(searchQuery) ||
      f.label.toLowerCase().includes(searchQuery) ||
      (f.hint && f.hint.toLowerCase().includes(searchQuery)) ||
      String(data[f.key] ?? "").toLowerCase().includes(searchQuery)
    );
  }
  if (showEmptyOnly) {
    visibleFields = visibleFields.filter((f) => {
      const v = data[f.key];
      return v === undefined || v === null || String(v).trim() === "";
    });
  }

  // 필터 결과 없으면 렌더링 안 함
  if ((searchQuery || showEmptyOnly) && visibleFields.length === 0) return null;

  return (
    <div id={`section-${section.id}`} className="border border-border rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 px-4 py-2.5 bg-secondary/30 hover:bg-secondary/50 transition-colors text-left"
      >
        {open ? <ChevronDown className="h-4 w-4 shrink-0" /> : <ChevronRight className="h-4 w-4 shrink-0" />}
        {section.icon && <span className="text-sm shrink-0">{section.icon}</span>}
        <span className="text-sm font-medium">{label}</span>
        <div className="flex items-center gap-2 ml-auto shrink-0">
          {/* 미니 프로그레스 바 */}
          <div className="w-12 h-1 bg-secondary rounded-full overflow-hidden hidden sm:block">
            <div
              className={cn("h-full rounded-full transition-all", allFilled ? "bg-green-400" : filledCount > 0 ? "bg-amber-400" : "bg-muted-foreground/20")}
              style={{ width: `${(filledCount / totalCount) * 100}%` }}
            />
          </div>
          <span className={cn(
            "text-[10px] font-mono tabular-nums",
            allFilled ? "text-green-400" : "text-muted-foreground",
          )}>
            {filledCount}/{totalCount}
          </span>
          {allFilled && <Check className="h-3 w-3 text-green-400" />}
          {!allFilled && !open && totalCount - filledCount > 0 && (
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-red-500/10 text-red-400 tabular-nums">
              {totalCount - filledCount}
            </span>
          )}
        </div>
      </button>
      {(open || (searchQuery && visibleFields.length > 0)) && (
        <div className="p-4 space-y-3">
          {visibleFields.map((field) => (
            <FieldEditor key={field.key} field={field} data={data} onChange={onChange} />
          ))}
        </div>
      )}
    </div>
  );
}

/* ── 프리뷰 패널 ── */
const ZOOM_LEVELS = [50, 75, 100, 125] as const;

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
  const [zoom, setZoom] = useState(100);
  const [showSource, setShowSource] = useState(false);
  const [copied, setCopied] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const maxKb = 102;
  const pct = Math.min((sizeKb / maxKb) * 100, 100);
  const isOver = sizeKb > maxKb;

  const copyHtml = () => {
    navigator.clipboard.writeText(html);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const openInNewTab = () => {
    const w = window.open();
    if (w) { w.document.write(html); w.document.close(); }
  };

  // 뉴스레터 HTML은 width=620px 고정 테이블 → 컨테이너보다 넓을 수 있음
  // iframe을 620px로 고정하고, 컨테이너 폭에 맞게 scale-down
  const CONTENT_WIDTH = 620;
  const [autoScale, setAutoScale] = useState(1);

  const updateScale = useCallback(() => {
    const container = containerRef.current;
    if (!container || mobileView) return;
    const availW = container.clientWidth - 8;
    if (availW < CONTENT_WIDTH && availW > 0) {
      setAutoScale(availW / CONTENT_WIDTH);
    } else {
      setAutoScale(1);
    }
  }, [mobileView]);

  useEffect(() => {
    updateScale();
    window.addEventListener("resize", updateScale);
    return () => window.removeEventListener("resize", updateScale);
  }, [updateScale]);

  const handleIframeLoad = useCallback(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;
    try {
      const h = iframe.contentDocument?.body?.scrollHeight;
      if (h && h > 0) iframe.style.height = `${h}px`;
    } catch {
      // sandbox cross-origin guard
    }
    updateScale();
  }, [updateScale]);

  return (
    <div className="flex flex-col h-full">
      {/* 상단 메타 */}
      <div className="flex items-center gap-2 pb-3 border-b border-border flex-nowrap">
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
      </div>

      {/* 도구 바 */}
      <div className="flex items-center gap-1 py-2 flex-nowrap overflow-x-auto scrollbar-hide">
        {/* 뷰포트 */}
        <button
          onClick={() => setMobileView(false)}
          className={cn("p-1.5 rounded shrink-0", !mobileView ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground")}
          title="Desktop"
        >
          <Monitor className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={() => setMobileView(true)}
          className={cn("p-1.5 rounded shrink-0", mobileView ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground")}
          title="Mobile (390px)"
        >
          <Smartphone className="h-3.5 w-3.5" />
        </button>
        <div className="w-px h-4 bg-border/40 mx-1 shrink-0" />
        {/* 줌 */}
        {ZOOM_LEVELS.map((z) => (
          <button
            key={z}
            onClick={() => setZoom(z)}
            className={cn(
              "px-1.5 py-1 text-[10px] rounded shrink-0 tabular-nums",
              zoom === z ? "bg-primary/10 text-primary font-medium" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {z}%
          </button>
        ))}
        <div className="w-px h-4 bg-border/40 mx-1 shrink-0" />
        {/* 소스/미리보기 토글 */}
        <button
          onClick={() => setShowSource(!showSource)}
          className={cn(
            "px-2 py-1 text-[10px] rounded shrink-0",
            showSource ? "bg-amber-500/10 text-amber-400" : "text-muted-foreground hover:text-foreground",
          )}
          title={showSource ? "Preview" : "Source"}
        >
          {showSource ? "Preview" : "Source"}
        </button>
        {/* 복사 */}
        {html && (
          <button
            onClick={copyHtml}
            className="p-1.5 rounded text-muted-foreground hover:text-foreground shrink-0"
            title="Copy HTML"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-green-400" /> : <Copy className="h-3.5 w-3.5" />}
          </button>
        )}
        {/* 새 탭 열기 */}
        {html && (
          <button
            onClick={openInNewTab}
            className="p-1.5 rounded text-muted-foreground hover:text-foreground shrink-0"
            title={lang === "ko" ? "새 탭에서 열기" : "Open in new tab"}
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* iframe or source */}
      <div ref={containerRef} className="flex-1 mt-1 flex justify-center overflow-auto bg-secondary/20 rounded-lg">
        {!html ? (
          <div className="flex items-center justify-center h-96 text-muted-foreground text-sm">
            {lang === "ko" ? "데이터를 입력하면 미리보기가 표시됩니다" : "Enter data to see preview"}
          </div>
        ) : showSource ? (
          <pre className="w-full p-4 text-[10px] font-mono text-muted-foreground overflow-auto whitespace-pre-wrap break-all max-h-[calc(100vh-16rem)]">
            {html}
          </pre>
        ) : (
          <iframe
            ref={iframeRef}
            srcDoc={html}
            onLoad={handleIframeLoad}
            className="border-0 bg-white rounded shadow-lg transition-all"
            style={{
              width: mobileView ? 390 : CONTENT_WIDTH,
              minHeight: 600,
              transform: zoom !== 100
                ? `scale(${zoom / 100})`
                : !mobileView && autoScale < 1
                  ? `scale(${autoScale})`
                  : undefined,
              transformOrigin: "top center",
            }}
            sandbox="allow-same-origin"
            title="Newsletter Preview"
          />
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
  const [searchQuery, setSearchQuery] = useState("");
  const [openSections, setOpenSections] = useState<Set<string>>(new Set(["basic"]));
  const [isDirty, setIsDirty] = useState(false);
  const [lastSavedData, setLastSavedData] = useState<Record<string, any>>({});
  const [showEmptyOnly, setShowEmptyOnly] = useState(false);
  const [schedule, setSchedule] = useState<any>(null);
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const searchInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // JSON 내보내기
  const exportJson = () => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `newsletter-vol${vol}-${editLang}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // JSON 가져오기
  const importJson = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const imported = JSON.parse(e.target?.result as string);
        if (typeof imported === "object" && imported !== null) {
          setData(imported);
          setIsDirty(true);
          toast(lang === "ko" ? "JSON 가져오기 완료" : "JSON imported", "success");
        }
      } catch {
        toast(lang === "ko" ? "JSON 파싱 실패" : "Invalid JSON", "error");
      }
    };
    reader.readAsText(file);
  };

  // 전체 열기/닫기
  const allOpen = openSections.size === SECTIONS.length;
  const toggleAllSections = () => {
    if (allOpen) {
      setOpenSections(new Set());
    } else {
      setOpenSections(new Set(SECTIONS.map((s) => s.id)));
    }
  };

  // 섹션 토글
  const toggleSection = useCallback((id: string) => {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  // 채움 통계
  const totalFields = useMemo(() => SECTIONS.reduce((n, s) => n + s.fields.length, 0), []);
  const filledFields = useMemo(() => {
    return SECTIONS.reduce((n, s) => {
      return n + s.fields.filter((f) => {
        const v = data[f.key];
        return v !== undefined && v !== null && String(v).trim() !== "";
      }).length;
    }, 0);
  }, [data]);

  // 초안 로드
  const { data: draftData, isLoading: draftLoading } = useQuery({
    queryKey: ["newsletter-draft", vol, editLang],
    queryFn: () => adminFetch<Record<string, any>>(`/admin/newsletter/draft?vol=${vol}&lang=${editLang}`),
    refetchOnWindowFocus: false,
  });

  // draftData 변경 시 data에 반영
  useEffect(() => {
    if (draftData) {
      setData(draftData);
      setLastSavedData(draftData);
      setIsDirty(false);
    }
  }, [draftData]);

  // 뉴스레터 발송 예약 상태 조회
  const fetchSchedule = useCallback(() => {
    adminFetch<any>("/admin/newsletter/schedule").then(setSchedule).catch(() => {});
  }, []);
  useEffect(() => { fetchSchedule(); }, [fetchSchedule]);

  // 키보드 단축키: Ctrl+S = 저장, Ctrl+Shift+F = 검색
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        saveMutation.mutate();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === "f" && e.shiftKey) {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  });

  // 미저장 상태에서 페이지 떠날 때 경고
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isDirty) { e.preventDefault(); }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isDirty]);

  // 자동 저장 (2분마다, dirty 상태일 때만)
  const autoSaveRef = useRef<ReturnType<typeof setInterval>>();
  useEffect(() => {
    clearInterval(autoSaveRef.current);
    autoSaveRef.current = setInterval(() => {
      if (isDirty && Object.keys(data).length > 0) {
        saveMutation.mutate();
      }
    }, 120_000);
    return () => clearInterval(autoSaveRef.current);
  }, [isDirty, data]);

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
    setIsDirty(true);
  }, []);

  // 저장
  const saveMutation = useMutation({
    mutationFn: () =>
      adminFetch("/admin/newsletter/draft", {
        method: "PUT",
        body: { vol, lang: editLang, data },
      }),
    onSuccess: () => {
      toast(lang === "ko" ? "초안 저장됨" : "Draft saved", "success");
      setLastSavedData(data);
      setIsDirty(false);
    },
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
          <h1 className="text-lg font-bold flex items-center gap-2">
            {t(lang, "admin_newsletter")}
            {isDirty && <span className="h-2 w-2 rounded-full bg-amber-400 animate-pulse" title="Unsaved changes" />}
          </h1>
          <div className="flex items-center gap-2 mt-0.5">
            <p className="text-xs text-muted-foreground">
              Vol.{vol} · {data.issue_date || "—"} · {filledFields}/{totalFields}
            </p>
            <div className="w-20 h-1.5 bg-secondary rounded-full overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-full transition-all",
                  filledFields === totalFields ? "bg-green-400" : filledFields > 0 ? "bg-primary" : "bg-muted-foreground/20",
                )}
                style={{ width: `${(filledFields / totalFields) * 100}%` }}
              />
            </div>
            <span className="text-[10px] text-muted-foreground tabular-nums">{Math.round((filledFields / totalFields) * 100)}%</span>
          </div>
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
            {/* 에디터 도구 바 */}
            <div className="flex items-center gap-2 pb-2 border-b border-border/40">
              {/* 검색 */}
              <div className="relative flex-1 min-w-0">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground/60" />
                <input
                  ref={searchInputRef}
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value.toLowerCase())}
                  placeholder={lang === "ko" ? "필드 검색 (Ctrl+Shift+F)" : "Search fields (Ctrl+Shift+F)"}
                  className="w-full pl-8 pr-8 py-1.5 text-xs bg-secondary/30 border border-border/40 rounded-md focus:outline-none focus:ring-1 focus:ring-primary placeholder:text-muted-foreground/40"
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery("")}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    <XCircle className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
              {/* 빈 필드만 보기 */}
              <button
                onClick={() => setShowEmptyOnly(!showEmptyOnly)}
                className={cn(
                  "flex items-center gap-1 px-2 py-1.5 text-xs border rounded-md transition-colors shrink-0",
                  showEmptyOnly
                    ? "bg-amber-500/10 border-amber-500/30 text-amber-400"
                    : "bg-secondary/30 border-border/40 text-muted-foreground hover:text-foreground hover:bg-secondary/50",
                )}
                title={lang === "ko" ? "빈 필드만 보기" : "Show empty only"}
              >
                <Filter className="h-3.5 w-3.5" />
              </button>
              {/* 전체 열기/닫기 */}
              <button
                onClick={toggleAllSections}
                className="flex items-center gap-1 px-2 py-1.5 text-xs text-muted-foreground hover:text-foreground bg-secondary/30 border border-border/40 rounded-md hover:bg-secondary/50 transition-colors shrink-0"
                title={allOpen ? "Collapse all" : "Expand all"}
              >
                <ChevronsUpDown className="h-3.5 w-3.5" />
              </button>
              {/* JSON export/import */}
              <button
                onClick={exportJson}
                className="p-1.5 text-xs text-muted-foreground hover:text-foreground bg-secondary/30 border border-border/40 rounded-md hover:bg-secondary/50 transition-colors shrink-0"
                title="Export JSON"
              >
                <Download className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="p-1.5 text-xs text-muted-foreground hover:text-foreground bg-secondary/30 border border-border/40 rounded-md hover:bg-secondary/50 transition-colors shrink-0"
                title="Import JSON"
              >
                <Upload className="h-3.5 w-3.5" />
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".json"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) importJson(f);
                  e.target.value = "";
                }}
              />
            </div>

            {SECTIONS.map((section) => (
              <CollapsibleSection
                key={section.id}
                section={section}
                lang={lang}
                data={data}
                onChange={handleChange}
                open={openSections.has(section.id)}
                onToggle={() => toggleSection(section.id)}
                searchQuery={searchQuery}
                showEmptyOnly={showEmptyOnly}
              />
            ))}

            {/* 액션 버튼 */}
            <div className="flex gap-3 pt-4 pb-8 sticky bottom-0 bg-background/80 backdrop-blur-sm z-10">
              <button
                onClick={() => saveMutation.mutate()}
                disabled={saveMutation.isPending}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 transition-colors relative",
                  isDirty
                    ? "bg-amber-500 text-white hover:bg-amber-600"
                    : "bg-primary text-primary-foreground hover:bg-primary/90",
                )}
              >
                {saveMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                {lang === "ko" ? "저장" : "Save"}
                <kbd className="hidden sm:inline text-[9px] opacity-60 ml-1 px-1 py-0.5 border border-current/20 rounded">
                  Ctrl+S
                </kbd>
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

            {/* 자동 발송 예약 상태 */}
            <div className="border border-border rounded-lg p-4 space-y-3">
              <h3 className="text-sm font-semibold flex items-center gap-2">
                <Clock className="h-4 w-4" />
                {lang === "ko" ? "자동 발송 예약" : "Auto-Send Schedule"}
              </h3>
              {schedule?.armed ? (
                <div className="space-y-2">
                  <p className="text-sm text-green-400 font-medium">
                    {"\u{1F7E2}"} Vol.{schedule.vol} {lang === "ko" ? "발송 예약됨" : "Scheduled"}
                  </p>
                  <div className="text-xs text-muted-foreground space-y-0.5">
                    <p>Asia: {schedule.schedule?.asia}</p>
                    <p>Europe: {schedule.schedule?.europe}</p>
                    <p>Americas: {schedule.schedule?.americas}</p>
                  </div>
                  {schedule.ttl_seconds > 0 && (
                    <p className="text-[10px] text-muted-foreground/60">
                      TTL: {Math.floor(schedule.ttl_seconds / 3600)}h {Math.floor((schedule.ttl_seconds % 3600) / 60)}m
                    </p>
                  )}
                  <button
                    disabled={scheduleLoading}
                    onClick={async () => {
                      setScheduleLoading(true);
                      try {
                        await adminFetch("/admin/newsletter/schedule", {
                          method: "POST",
                          body: { vol: schedule.vol, action: "disarm" },
                        });
                        toast(lang === "ko" ? "자동 발송 취소됨" : "Schedule disarmed", "success");
                        fetchSchedule();
                      } catch { toast(lang === "ko" ? "취소 실패" : "Failed", "error"); }
                      setScheduleLoading(false);
                    }}
                    className="flex items-center gap-2 px-3 py-1.5 bg-secondary text-foreground rounded-lg text-xs font-medium hover:bg-secondary/80 disabled:opacity-50"
                  >
                    {scheduleLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <XCircle className="h-3 w-3" />}
                    {lang === "ko" ? "예약 취소" : "Disarm"}
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">
                    {"\u26AA"} {lang === "ko" ? "자동 발송 미예약" : "No schedule armed"}
                  </p>
                  <button
                    disabled={scheduleLoading}
                    onClick={async () => {
                      setScheduleLoading(true);
                      try {
                        await adminFetch("/admin/newsletter/schedule", {
                          method: "POST",
                          body: { vol, action: "arm" },
                        });
                        toast(lang === "ko" ? `Vol.${vol} 자동 발송 예약됨` : `Vol.${vol} scheduled`, "success");
                        fetchSchedule();
                      } catch { toast(lang === "ko" ? "예약 실패" : "Failed", "error"); }
                      setScheduleLoading(false);
                    }}
                    className="flex items-center gap-2 px-3 py-1.5 bg-primary text-primary-foreground rounded-lg text-xs font-medium hover:bg-primary/90 disabled:opacity-50"
                  >
                    {scheduleLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <CheckCircle className="h-3 w-3" />}
                    {lang === "ko" ? `Vol.${vol} 예약하기` : `Schedule Vol.${vol}`}
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
