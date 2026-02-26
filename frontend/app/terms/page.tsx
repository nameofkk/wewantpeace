"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";

const SECTIONS_KO = [
  {
    title: "제1조 (목적)",
    content: `이 약관은 도핑연구소(이하 "회사")가 제공하는 wewantpeace 서비스의 이용조건 및 절차, 회사와 이용자의 권리·의무 및 책임사항을 규정함을 목적으로 합니다.`,
  },
  {
    title: "제2조 (정의)",
    content: `① "서비스"란 회사가 제공하는 세계정세 알림·지도·커뮤니티 플랫폼(wewantpeace)을 말합니다.\n② "회원"이란 본 약관에 동의하고 서비스를 이용하는 자를 말합니다.\n③ "Pro 회원"이란 유료 구독을 통해 추가 기능을 이용하는 회원을 말합니다.\n④ "콘텐츠"란 회원이 서비스 내에서 작성·게시한 게시물, 댓글 등을 말합니다.`,
  },
  {
    title: "제3조 (서비스 제공 및 변경)",
    content: `① 회사는 연중무휴 24시간 서비스를 제공합니다.\n② 회사는 서비스 내용을 변경할 경우 최소 7일 전에 공지합니다.\n③ 정기점검 등 기술상 이유로 서비스가 일시 중단될 수 있습니다.`,
  },
  {
    title: "제4조 (이용계약 체결)",
    content: `① 서비스 이용은 만 14세 이상만 가능합니다.\n② 이용자는 회원가입 시 본 약관 및 개인정보처리방침에 동의해야 합니다.\n③ 허위 정보 제공 시 이용이 제한될 수 있습니다.\n④ 회원은 언제든 서비스 내 설정에서 회원 탈퇴를 할 수 있습니다.`,
  },
  {
    title: "제5조 (회원 의무 및 금지행위)",
    content: `① 회원 인증은 Firebase Authentication(Google 소셜 로그인 포함)을 통해 이루어집니다.\n② 회원은 다음 행위를 해서는 안 됩니다:\n  1) 타인의 계정 도용 또는 허위 정보 등록\n  2) 허위 뉴스, 선동적 콘텐츠 게시\n  3) 스팸, 광고성 게시물 반복 게시\n  4) 저작권 침해 콘텐츠 게시\n  5) 혐오 발언, 명예훼손 발언\n  6) 서비스 해킹 또는 비정상적 접근 시도\n  7) 다중 계정 생성 및 어뷰징`,
  },
  {
    title: "제6조 (서비스 제공자 의무)",
    content: `① 회사는 안정적인 서비스 제공을 위해 최선을 다합니다.\n② 회사는 이용자의 개인정보를 개인정보처리방침에 따라 보호합니다.\n③ 회원의 불만·피해 구제에 최선을 다합니다.`,
  },
  {
    title: "제7조 (유료서비스 및 결제)",
    content: `① Pro 구독: 월 4,900원 / Pro+ 구독: 월 9,900원 (VAT 포함)\n② 결제는 Google Play 또는 Apple App Store 인앱결제(IAP)로 처리됩니다.\n③ 구독 취소는 각 스토어(Google Play/App Store)에서 직접 진행하며, 취소 시 현재 기간 만료까지 서비스 이용 가능합니다.\n④ 결제 관련 문의: krshin7@naver.com`,
  },
  {
    title: "제8조 (책임제한)",
    content: `① 천재지변, 불가항력에 의한 서비스 장애는 회사 책임에서 제외됩니다.\n② Firebase, Google Play, Apple App Store 등 제3자 서비스 장애는 회사 책임에서 제외됩니다.\n③ 이용자 귀책으로 발생한 손해는 회사가 책임지지 않습니다.`,
  },
  {
    title: "제9조 (분쟁해결)",
    content: `서비스 이용 관련 분쟁은 한국소비자원 또는 전자거래분쟁조정위원회를 통해 해결할 수 있습니다.`,
  },
  {
    title: "제10조 (준거법 및 관할)",
    content: `본 약관은 대한민국 법률을 준거법으로 하며, 분쟁 시 서울중앙지방법원을 전속 관할로 합니다.`,
  },
  {
    title: "제11조 (회원 탈퇴 및 계정 삭제)",
    content: `① 회원은 설정 > 계정에서 언제든 회원 탈퇴를 할 수 있습니다.\n② 탈퇴 즉시 개인정보(이메일, 닉네임, 생년도 등)는 익명화 또는 삭제됩니다.\n③ 구독 중인 유료서비스(Pro/Pro+)는 Google Play 또는 App Store에서 별도로 취소해야 합니다. 탈퇴만으로는 구독이 자동 해지되지 않습니다.\n④ 관련 법령에 따른 보관 의무가 있는 데이터(결제 기록 등)는 해당 기간 동안 보관 후 파기합니다.\n⑤ 탈퇴 후 동일 계정(Firebase UID)으로 재가입할 수 없습니다.`,
  },
  {
    title: "제12조 (미성년자 보호)",
    content: `① 만 14세 미만의 아동은 본 서비스에 가입할 수 없습니다.\n② 회원가입 시 생년도를 확인하여 만 14세 미만인 경우 가입이 거부됩니다.\n③ 만 14세 미만 아동의 개인정보가 수집된 사실을 인지한 경우, 해당 정보를 즉시 삭제합니다.`,
  },
];

const SECTIONS_EN = [
  {
    title: "Article 1 (Purpose)",
    content: `These Terms govern the conditions, procedures, rights, obligations, and responsibilities between 도핑연구소 ("Company") and users of the wewantpeace service.`,
  },
  {
    title: "Article 2 (Definitions)",
    content: `① "Service" means the global situation alert, map, and community platform (wewantpeace) provided by the Company.\n② "Member" means a person who agrees to these Terms and uses the Service.\n③ "Pro Member" means a member using additional features through a paid subscription.\n④ "Content" means posts, comments, and other material created by members within the Service.`,
  },
  {
    title: "Article 3 (Service Provision and Changes)",
    content: `① The Company provides the Service 24 hours a day, 365 days a year.\n② The Company will notify users at least 7 days in advance of any changes to the Service.\n③ The Service may be temporarily suspended for technical reasons such as scheduled maintenance.`,
  },
  {
    title: "Article 4 (Service Agreement)",
    content: `① The Service is available only to users aged 14 and above.\n② Users must agree to these Terms and the Privacy Policy when registering.\n③ Providing false information may result in restricted access.\n④ Members may withdraw from the Service at any time through the Settings menu.`,
  },
  {
    title: "Article 5 (Member Obligations and Prohibited Conduct)",
    content: `① Member authentication is performed through Firebase Authentication (including Google social login).\n② Members must not:\n  1) Steal another person's account or register false information\n  2) Post fake news or inflammatory content\n  3) Repeatedly post spam or promotional material\n  4) Post content that infringes copyright\n  5) Make hateful or defamatory statements\n  6) Attempt to hack or access the Service abnormally\n  7) Create multiple accounts or engage in abusive behavior`,
  },
  {
    title: "Article 6 (Company Obligations)",
    content: `① The Company will make best efforts to provide a stable Service.\n② The Company will protect user personal information in accordance with the Privacy Policy.\n③ The Company will make best efforts to handle member complaints and remedy damages.`,
  },
  {
    title: "Article 7 (Paid Services and Payment)",
    content: `① Pro subscription: ₩4,900/month / Pro+ subscription: ₩9,900/month (VAT included)\n② Payment is processed via Google Play or Apple App Store in-app purchase (IAP).\n③ Cancellation must be done through the respective store (Google Play/App Store). Upon cancellation, the Service remains accessible until the end of the current billing period.\n④ Payment inquiries: krshin7@naver.com`,
  },
  {
    title: "Article 8 (Limitation of Liability)",
    content: `① Service disruptions caused by natural disasters or force majeure are excluded from Company liability.\n② Service disruptions of third-party services such as Firebase, Google Play, or Apple App Store are excluded from Company liability.\n③ The Company is not liable for damages caused by the user's own actions.`,
  },
  {
    title: "Article 9 (Dispute Resolution)",
    content: `Disputes arising from use of the Service may be resolved through the Korea Consumer Agency or the Electronic Commerce Dispute Mediation Committee.`,
  },
  {
    title: "Article 10 (Governing Law and Jurisdiction)",
    content: `These Terms are governed by the laws of the Republic of Korea. Disputes shall be subject to the exclusive jurisdiction of the Seoul Central District Court.`,
  },
  {
    title: "Article 11 (Account Deletion and Withdrawal)",
    content: `① Members may delete their account at any time through Settings > Account.\n② Upon deletion, personal information (email, nickname, birth year, etc.) is immediately anonymized or deleted.\n③ Active paid subscriptions (Pro/Pro+) must be canceled separately through Google Play or App Store. Account deletion alone does not cancel subscriptions.\n④ Data subject to legal retention requirements (e.g., payment records) will be retained for the required period and then destroyed.\n⑤ After deletion, re-registration with the same account (Firebase UID) is not possible.`,
  },
  {
    title: "Article 12 (Protection of Minors)",
    content: `① Children under the age of 14 may not register for this Service.\n② Birth year is verified during registration, and registration is denied for users under 14.\n③ If we become aware that personal information of a child under 14 has been collected, it will be deleted immediately.`,
  },
];

export default function TermsPage() {
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
          <h1 className="text-xl font-bold">{t(lang, "terms_title")}</h1>
        </div>

        <p className="text-sm text-muted-foreground mb-6">
          {t(lang, "terms_date")}
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

          <div className="rounded-xl border border-border bg-card p-5">
            <h2 className="text-sm font-bold mb-3 text-primary">{t(lang, "terms_addendum")}</h2>
            <p className="text-sm text-muted-foreground">
              {t(lang, "terms_addendum_text")}
            </p>
          </div>
        </div>

        <div className="mt-8 text-center text-xs text-muted-foreground">
          {t(lang, "terms_contact")}:{" "}
          <a href="mailto:krshin7@naver.com" className="hover:underline">
            krshin7@naver.com
          </a>
          {" · "}
          <Link href="/privacy" className="hover:underline">{t(lang, "terms_privacy_link")}</Link>
        </div>
      </div>
    </div>
  );
}
