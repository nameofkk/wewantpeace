"use client";

import { useState } from "react";
import { useAppStore } from "@/lib/store";
import { BookOpen, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface GuideSection {
  id: string;
  titleKo: string;
  titleEn: string;
  bodyKo: string;
  bodyEn: string;
}

const SECTIONS: GuideSection[] = [
  {
    id: "dashboard",
    titleKo: "대시보드",
    titleEn: "Dashboard",
    bodyKo: "전체 서비스 핵심 지표를 한눈에 확인합니다. 신규 가입, 활성 사용자, 구독 현황, 최근 이슈 클러스터 등의 요약 정보를 제공합니다.",
    bodyEn: "Overview of key service metrics at a glance. Shows new signups, active users, subscription status, and recent issue clusters.",
  },
  {
    id: "users",
    titleKo: "사용자 관리",
    titleEn: "Users",
    bodyKo: "전체 사용자 목록을 조회하고 검색, 필터링합니다. 사용자의 플랜 변경, 상태 변경(활성/정지/삭제), 관심 지역 확인이 가능합니다.",
    bodyEn: "Browse, search, and filter all users. Change plans, update status (active/suspended/deleted), and view interest areas.",
  },
  {
    id: "subscriptions",
    titleKo: "구독 관리",
    titleEn: "Subscriptions",
    bodyKo: "유료 구독 현황을 관리합니다. 플랜별 분포, 트라이얼 현황, 만료 예정, 결제 이력을 확인합니다.",
    bodyEn: "Manage paid subscriptions. View plan distribution, trial status, upcoming expirations, and payment history.",
  },
  {
    id: "marketing",
    titleKo: "마케팅",
    titleEn: "Marketing",
    bodyKo: "마케팅 동의 사용자 관리, 주간 리포트 이메일 발송 현황, 캠페인 성과를 추적합니다.",
    bodyEn: "Manage marketing-opted users, track weekly report email delivery, and monitor campaign performance.",
  },
  {
    id: "posts",
    titleKo: "게시글 관리",
    titleEn: "Posts",
    bodyKo: "커뮤니티 게시글을 모니터링합니다. 신고된 글 우선 표시, 숨김/삭제 처리, 작성자 정보 확인이 가능합니다.",
    bodyEn: "Monitor community posts. Prioritize reported content, hide/delete posts, and view author details.",
  },
  {
    id: "comments",
    titleKo: "댓글 관리",
    titleEn: "Comments",
    bodyKo: "커뮤니티 댓글을 모니터링합니다. 신고된 댓글을 우선 확인하고 숨김/삭제 처리합니다.",
    bodyEn: "Monitor community comments. Review reported comments and hide/delete as needed.",
  },
  {
    id: "reports",
    titleKo: "신고 관리",
    titleEn: "Reports",
    bodyKo: "사용자 신고 목록을 처리합니다. 신고 사유 확인, 대상 콘텐츠 조회, 처리 상태(대기/승인/반려) 변경이 가능합니다.",
    bodyEn: "Process user reports. View reasons, check target content, and update status (pending/approved/rejected).",
  },
  {
    id: "feedbacks",
    titleKo: "피드백",
    titleEn: "Feedbacks",
    bodyKo: "사용자 피드백을 확인합니다. 유형별(버그/기능요청/기타) 필터링, 상태 관리(신규/확인/완료)가 가능합니다.",
    bodyEn: "Review user feedback. Filter by type (bug/feature/other) and manage status (new/reviewed/done).",
  },
  {
    id: "pipeline",
    titleKo: "파이프라인",
    titleEn: "Pipeline",
    bodyKo: "데이터 수집→정규화→중복제거→클러스터링→KScore 알림→트렌딩 계산 전체 파이프라인의 건강 상태를 모니터링합니다.",
    bodyEn: "Monitor the full data pipeline health: collection → normalization → dedup → clustering → KScore alerts → trending.",
  },
  {
    id: "clusters",
    titleKo: "클러스터 관리",
    titleEn: "Clusters",
    bodyKo: "이슈 클러스터 목록을 조회합니다. severity, kscore 기준 정렬, 토픽/국가 필터, 클러스터 상세(이벤트 목록, 타임라인)를 확인합니다.",
    bodyEn: "Browse issue clusters sorted by severity/kscore. Filter by topic/country and view cluster details (events, timeline).",
  },
  {
    id: "events",
    titleKo: "이벤트 관리",
    titleEn: "Events",
    bodyKo: "정규화된 이벤트(NormalizedEvent) 목록을 조회합니다. 원문, 번역, 토픽, 위치, severity 등 상세 정보를 확인합니다.",
    bodyEn: "Browse normalized events. View original text, translation, topic, location, severity, and other details.",
  },
  {
    id: "sources",
    titleKo: "소스 관리",
    titleEn: "Sources",
    bodyKo: "RSS/Telegram 소스 채널을 관리합니다. 티어(A~D) 설정, 활성/비활성 전환, 최근 수집 현황을 확인합니다.",
    bodyEn: "Manage RSS/Telegram source channels. Set tiers (A-D), toggle active status, and check recent collection stats.",
  },
  {
    id: "kpi",
    titleKo: "KPI 대시보드",
    titleEn: "KPI Dashboard",
    bodyKo: "주간 KPI 스냅샷을 관리합니다. A1 온보딩율, 페이월 전환율, 트라이얼→유료 전환율, D7 리텐션, WoW 변화율을 추적합니다. 수동 스냅샷 생성도 가능합니다.",
    bodyEn: "Manage weekly KPI snapshots. Track A1 onboarding, paywall conversion, trial-to-paid, D7 retention, and WoW changes. Manual snapshot generation available.",
  },
  {
    id: "trending",
    titleKo: "트렌딩",
    titleEn: "Trending",
    bodyKo: "글로벌 트렌딩 키워드와 핫 이슈를 확인합니다. kscore 기반 순위, 시간대별 추이를 모니터링합니다.",
    bodyEn: "View global trending keywords and hot issues. Monitor kscore-based rankings and time-based trends.",
  },
  {
    id: "tension",
    titleKo: "긴장도 지수",
    titleEn: "Tension Index",
    bodyKo: "국가별 긴장도 지수를 확인합니다. 실시간 긴장도 레벨, 히스토리 차트, 임계값 알림 설정을 관리합니다.",
    bodyEn: "View per-country tension indices. Monitor real-time levels, history charts, and manage threshold alerts.",
  },
  {
    id: "settings",
    titleKo: "설정",
    titleEn: "Settings",
    bodyKo: "어드민 시스템 설정을 관리합니다. 글로벌 설정값(KScore 알림 임계값, 푸시 설정 등)을 JSON으로 편집합니다.",
    bodyEn: "Manage admin system settings. Edit global config values (KScore alert thresholds, push settings, etc.) in JSON format.",
  },
  {
    id: "logs",
    titleKo: "어드민 로그",
    titleEn: "Admin Logs",
    bodyKo: "모든 어드민 액션(사용자 수정, 설정 변경, 콘텐츠 삭제 등)의 감사 로그를 확인합니다.",
    bodyEn: "View audit logs for all admin actions (user changes, settings updates, content deletions, etc.).",
  },
  {
    id: "partners",
    titleKo: "파트너 관리",
    titleEn: "Partners",
    bodyKo: "파트너 CRM입니다. 잠재→연락→협상→활성→이탈/거절 단계별로 파트너를 관리합니다. 팔로업 날짜, URL, 메모를 기록합니다.",
    bodyEn: "Partner CRM. Manage partners through prospect → contacted → negotiating → active → churned/rejected stages. Track follow-ups, URLs, and notes.",
  },
  {
    id: "links",
    titleKo: "단축 링크",
    titleEn: "Short Links",
    bodyKo: "마케팅 단축 링크를 생성하고 클릭 수를 추적합니다. UTM 파라미터 자동 부착, 만료일 설정이 가능합니다.",
    bodyEn: "Create marketing short links and track clicks. Auto-attach UTM parameters and set expiration dates.",
  },
  {
    id: "marketing",
    titleKo: "마케팅 (레퍼럴 포함)",
    titleEn: "Marketing (incl. Referral)",
    bodyKo: "마케팅 캠페인, 링크 클릭, 레퍼럴 성과를 종합적으로 분석합니다. 기간별 비교, 채널별 성과를 확인합니다.",
    bodyEn: "Analyze marketing campaigns, link clicks, and referral performance. Compare periods and view per-channel metrics.",
  },
];

function CollapsibleSection({
  section,
  lang,
  isOpen,
  onToggle,
}: {
  section: GuideSection;
  lang: "ko" | "en";
  isOpen: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="border border-border/50 rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium hover:bg-secondary/30 transition-colors"
      >
        <span>{lang === "ko" ? section.titleKo : section.titleEn}</span>
        <ChevronDown
          className={cn(
            "h-4 w-4 text-muted-foreground transition-transform",
            isOpen && "rotate-180"
          )}
        />
      </button>
      {isOpen && (
        <div className="px-4 pb-4 text-sm text-muted-foreground leading-relaxed">
          {lang === "ko" ? section.bodyKo : section.bodyEn}
        </div>
      )}
    </div>
  );
}

export default function AdminGuidePage() {
  const { lang } = useAppStore();
  const [openSections, setOpenSections] = useState<Set<string>>(new Set());

  const toggle = (id: string) => {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const expandAll = () => setOpenSections(new Set(SECTIONS.map((s) => s.id)));
  const collapseAll = () => setOpenSections(new Set());

  return (
    <div>
      <div className="mb-6 flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <BookOpen className="h-6 w-6 text-primary" />
            {lang === "ko" ? "어드민 가이드" : "Admin Guide"}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {lang === "ko"
              ? `전체 ${SECTIONS.length}개 섹션`
              : `${SECTIONS.length} sections total`}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={expandAll}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-secondary text-muted-foreground hover:text-foreground transition-colors"
          >
            {lang === "ko" ? "모두 펼치기" : "Expand All"}
          </button>
          <button
            onClick={collapseAll}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-secondary text-muted-foreground hover:text-foreground transition-colors"
          >
            {lang === "ko" ? "모두 접기" : "Collapse All"}
          </button>
        </div>
      </div>

      <div className="space-y-2">
        {SECTIONS.map((section) => (
          <CollapsibleSection
            key={section.id}
            section={section}
            lang={lang}
            isOpen={openSections.has(section.id)}
            onToggle={() => toggle(section.id)}
          />
        ))}
      </div>
    </div>
  );
}
