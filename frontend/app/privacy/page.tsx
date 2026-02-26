"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";

const SECTIONS_KO = [
  {
    title: "1. 수집하는 개인정보 항목",
    content: `[필수] 이메일 주소 (Google 로그인 시 자동 수집), 닉네임, 생년도, 소셜로그인 식별자(Google UID 등)\n[선택] 프로필 사진, 자기소개(bio)\n[자동] IP주소, 접속 로그, 쿠키, 서비스 이용 기록`,
  },
  {
    title: "2. 수집 목적 및 이용 목적",
    content: `• 회원 가입 및 관리\n• 서비스 제공 및 개인화\n• 유료 서비스 결제 처리\n• 불법 이용 방지 및 보안\n• 서비스 개선을 위한 통계 분석`,
  },
  {
    title: "3. 보유 및 이용 기간",
    content: `• 회원 탈퇴 시 즉시 파기 (닉네임 및 이메일 익명 처리)\n• 회원 탈퇴 방법: 설정 > 계정 > 회원 탈퇴 버튼 클릭\n• 단, 관련 법령에 따라 보관:\n  - 계약/청약 철회 기록: 5년 (전자상거래법)\n  - 소비자 불만 처리: 3년 (전자상거래법)\n  - 부정 이용 방지: 1년`,
  },
  {
    title: "4. 개인정보 제3자 제공",
    content: `• Firebase (Google Inc.): 인증 서비스 제공 목적\n• Google Play / Apple App Store: 인앱결제(IAP) 처리 목적\n• 법령에 따른 수사기관 요청 시 제공 가능`,
  },
  {
    title: "5. 개인정보 처리 위탁",
    content: `• 클라우드 인프라: Railway (서버 운영)\n• 위탁 업무 외 개인정보 처리 금지 계약 체결`,
  },
  {
    title: "6. 이용자 권리 행사 방법",
    content: `이용자는 언제든지 다음 권리를 행사할 수 있습니다:\n• 개인정보 열람, 정정, 삭제 요청\n• 개인정보 처리 정지 요청\n• 데이터 삭제 요청 방법:\n  1) 앱 내 설정 > 계정 > 회원 탈퇴\n  2) 이메일 요청: krshin7@naver.com\n• 요청 처리: 14일 이내`,
  },
  {
    title: "7. 자동 수집 장치 (쿠키)",
    content: `• 세션 관리 및 서비스 이용 분석에 쿠키 사용\n• 브라우저 설정으로 쿠키 거부 가능 (일부 서비스 제한 가능)`,
  },
  {
    title: "8. 개인정보 안전성 확보 조치",
    content: `• 개인정보 전송 시 HTTPS(TLS) 암호화\n• 접근 권한 최소화 (역할 기반 접근 제어)\n• 비밀번호 해시화 저장\n• 정기적 보안 점검`,
  },
  {
    title: "9. 개인정보 보호책임자",
    content: `운영사: 도핑연구소\n서비스명: wewantpeace\n이메일: krshin7@naver.com`,
  },
  {
    title: "10. 고지의 의무",
    content: `이 개인정보처리방침은 변경될 경우 서비스 내 공지사항 또는 이메일을 통해 사전 고지합니다.`,
  },
  {
    title: "11. 아동 보호",
    content: `① 만 14세 미만 아동의 개인정보는 수집하지 않습니다.\n② 회원가입 시 생년도를 확인하여 만 14세 미만인 경우 가입을 제한합니다.\n③ 만 14세 미만 아동의 개인정보가 수집된 사실을 인지한 경우, 해당 정보를 즉시 삭제하고 해당 계정을 비활성화합니다.`,
  },
  {
    title: "12. 개인정보의 해외 이전",
    content: `서비스 제공을 위해 다음과 같이 개인정보가 해외로 이전될 수 있습니다:\n• Firebase Authentication (Google LLC, 미국): 회원 인증 및 관리\n• Google Play (Google LLC, 미국): 인앱결제 처리 및 구독 관리\n• 이전되는 항목: Firebase UID, 이메일 주소, 결제 정보\n• 이전 방법: 네트워크를 통한 전송\n• 해당 업체의 개인정보보호 정책에 따라 보호됩니다.`,
  },
];

const SECTIONS_EN = [
  {
    title: "1. Personal Information Collected",
    content: `[Required] Email address (automatically collected via Google login), nickname, birth year, social login identifier (Google UID, etc.)\n[Optional] Profile photo, bio\n[Automatic] IP address, access logs, cookies, service usage records`,
  },
  {
    title: "2. Purpose of Collection and Use",
    content: `• Membership registration and management\n• Service provision and personalization\n• Payment processing for paid services\n• Prevention of illegal use and security\n• Statistical analysis for service improvement`,
  },
  {
    title: "3. Retention and Use Period",
    content: `• Immediately destroyed upon membership withdrawal (nickname and email anonymized)\n• How to withdraw: Settings > Account > Delete Account\n• Retained as required by law:\n  - Contract/subscription withdrawal records: 5 years (E-Commerce Act)\n  - Consumer complaint handling: 3 years (E-Commerce Act)\n  - Abuse prevention: 1 year`,
  },
  {
    title: "4. Third-Party Provision of Personal Information",
    content: `• Firebase (Google Inc.): for authentication services\n• Google Play / Apple App Store: for in-app purchase (IAP) processing\n• May be provided to law enforcement agencies upon lawful request`,
  },
  {
    title: "5. Entrustment of Personal Information Processing",
    content: `• Cloud infrastructure: Railway (server operation)\n• Contracts in place prohibiting processing beyond the entrusted work`,
  },
  {
    title: "6. How to Exercise User Rights",
    content: `Users may exercise the following rights at any time:\n• Request access, correction, or deletion of personal information\n• Request suspension of personal information processing\n• How to request data deletion:\n  1) In-app: Settings > Account > Delete Account\n  2) Email: krshin7@naver.com\n• Requests handled within 14 days`,
  },
  {
    title: "7. Automated Collection Devices (Cookies)",
    content: `• Cookies are used for session management and service usage analysis\n• Cookies can be refused via browser settings (some services may be limited)`,
  },
  {
    title: "8. Security Measures",
    content: `• HTTPS (TLS) encryption for data transmission\n• Minimum access privileges (role-based access control)\n• Hashed password storage\n• Regular security audits`,
  },
  {
    title: "9. Privacy Officer",
    content: `Operator: 도핑연구소\nService: wewantpeace\nEmail: krshin7@naver.com`,
  },
  {
    title: "10. Notification of Changes",
    content: `If this Privacy Policy is updated, users will be notified via in-service announcements or email in advance.`,
  },
  {
    title: "11. Protection of Children",
    content: `① We do not collect personal information from children under the age of 14.\n② Birth year is verified during registration, and registration is denied for users under 14.\n③ If we become aware that personal information of a child under 14 has been collected, the information will be immediately deleted and the account deactivated.`,
  },
  {
    title: "12. International Transfer of Personal Information",
    content: `Personal information may be transferred overseas to provide the Service:\n• Firebase Authentication (Google LLC, USA): member authentication and management\n• Google Play (Google LLC, USA): in-app purchase processing and subscription management\n• Items transferred: Firebase UID, email address, payment information\n• Transfer method: transmission via network\n• Protected under each provider's privacy policies.`,
  },
];

export default function PrivacyPage() {
  const lang = useAppStore((s) => s.lang);
  const router = useRouter();
  const sections = lang === "en" ? SECTIONS_EN : SECTIONS_KO;

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-2xl px-4 py-8">
        <div className="flex items-center gap-2 mb-6">
          <button onClick={() => router.back()} className="text-muted-foreground hover:text-foreground">
            <ChevronLeft className="h-5 w-5" />
          </button>
          <h1 className="text-xl font-bold">{t(lang, "privacy_title")}</h1>
        </div>

        <p className="text-sm text-muted-foreground mb-2">
          {t(lang, "privacy_date")}
        </p>
        <p className="text-sm text-muted-foreground mb-6">
          {t(lang, "privacy_compliance")}
        </p>

        <div className="space-y-6">
          {sections.map((section) => (
            <div key={section.title} className="rounded-xl border border-border bg-card p-5">
              <h2 className="text-sm font-bold mb-3 text-primary">{section.title}</h2>
              <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-line">
                {section.content}
              </p>
            </div>
          ))}
        </div>

        <div className="mt-8 text-center text-xs text-muted-foreground">
          {t(lang, "privacy_contact")}:{" "}
          <a href="mailto:krshin7@naver.com" className="hover:underline">
            krshin7@naver.com
          </a>
          {" · "}
          <Link href="/terms" className="hover:underline">{t(lang, "privacy_terms_link")}</Link>
        </div>
      </div>
    </div>
  );
}
