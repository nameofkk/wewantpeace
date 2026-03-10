/** 나중에 커스텀 도메인 이메일로 교체할 때 여기만 변경 */
export const CONTACT_EMAIL = "krshin7@gmail.com";

export const TERMS_KO = [
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
    content: `① Pro 구독: 월 4,900원 / Pro+ 구독: 월 9,900원 (VAT 포함)\n② 결제는 Google Play 또는 Apple App Store 인앱결제(IAP)로 처리됩니다.\n③ 구독 취소는 각 스토어(Google Play/App Store)에서 직접 진행하며, 취소 시 현재 기간 만료까지 서비스 이용 가능합니다.\n④ 결제 관련 문의: ${CONTACT_EMAIL}`,
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

export const TERMS_EN = [
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
    content: `① Pro subscription: ₩4,900/month / Pro+ subscription: ₩9,900/month (VAT included)\n② Payment is processed via Google Play or Apple App Store in-app purchase (IAP).\n③ Cancellation must be done through the respective store (Google Play/App Store). Upon cancellation, the Service remains accessible until the end of the current billing period.\n④ Payment inquiries: ${CONTACT_EMAIL}`,
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

export const PRIVACY_KO = [
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
    content: `이용자는 언제든지 다음 권리를 행사할 수 있습니다:\n• 개인정보 열람, 정정, 삭제 요청\n• 개인정보 처리 정지 요청\n• 데이터 삭제 요청 방법:\n  1) 앱 내 설정 > 계정 > 회원 탈퇴\n  2) 이메일 요청: ${CONTACT_EMAIL}\n• 요청 처리: 14일 이내`,
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
    content: `운영사: 도핑연구소\n서비스명: wewantpeace\n이메일: ${CONTACT_EMAIL}`,
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

export const PRIVACY_EN = [
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
    content: `Users may exercise the following rights at any time:\n• Request access, correction, or deletion of personal information\n• Request suspension of personal information processing\n• How to request data deletion:\n  1) In-app: Settings > Account > Delete Account\n  2) Email: ${CONTACT_EMAIL}\n• Requests handled within 14 days`,
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
    content: `Operator: 도핑연구소\nService: wewantpeace\nEmail: ${CONTACT_EMAIL}`,
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

export const REFUND_KO = [
  {
    title: "1. 환불 정책 개요",
    content: `wewantpeace는 구독 기반 SaaS 서비스입니다. 본 환불 정책은 유료 구독(Pro, Pro+)에 적용됩니다.\n무료(Free/BASIC) 플랜은 결제가 없으므로 환불 대상이 아닙니다.`,
  },
  {
    title: "2. 구독 취소",
    content: `① 회원은 언제든지 설정 > 구독 관리에서 구독을 취소할 수 있습니다.\n② 구독 취소 시 현재 결제 기간이 끝날 때까지 Pro/Pro+ 기능을 계속 이용할 수 있습니다.\n③ 결제 기간 만료 후 자동으로 무료 플랜으로 전환됩니다.\n④ 구독 취소는 즉시 처리되며, 다음 결제일부터 요금이 청구되지 않습니다.`,
  },
  {
    title: "3. 환불 요청",
    content: `① 결제일로부터 7일 이내에 환불을 요청하면 전액 환불해 드립니다.\n② 7일 이후에는 환불이 제공되지 않으며, 구독 취소만 가능합니다.\n③ 환불 요청은 이메일(${CONTACT_EMAIL})로 접수해 주세요.\n④ 환불 처리는 요청일로부터 영업일 기준 7일 이내에 완료됩니다.`,
  },
  {
    title: "4. 환불 불가 사유",
    content: `다음의 경우 환불이 제공되지 않습니다:\n• 결제일로부터 7일이 경과한 경우\n• 서비스를 상당 부분 이용한 경우\n• 이용약관 위반으로 계정이 정지된 경우\n• 회원의 단순 변심에 의한 요청 (7일 이내 제외)`,
  },
  {
    title: "5. 플랜 변경",
    content: `① Pro에서 Pro+로 업그레이드 시 차액이 즉시 청구됩니다.\n② Pro+에서 Pro로 다운그레이드 시 현재 결제 기간 만료 후 적용됩니다.\n③ 플랜 변경은 설정 > 구독 관리에서 진행할 수 있습니다.`,
  },
  {
    title: "6. 문의",
    content: `환불 관련 문의: ${CONTACT_EMAIL}\n처리 시간: 영업일 기준 1~3일 이내 답변`,
  },
];

export const REFUND_EN = [
  {
    title: "1. Refund Policy Overview",
    content: `WeWantPeace is a subscription-based SaaS service. This refund policy applies to paid subscriptions (Pro, Pro+).\nThe free (Free/BASIC) plan involves no payment and is not subject to refunds.`,
  },
  {
    title: "2. Subscription Cancellation",
    content: `① Members may cancel their subscription at any time via Settings > Subscription Management.\n② Upon cancellation, Pro/Pro+ features remain accessible until the end of the current billing period.\n③ After the billing period expires, the account automatically reverts to the free plan.\n④ Cancellations are processed immediately, and no charges will be made from the next billing date.`,
  },
  {
    title: "3. Refund Requests",
    content: `① Full refunds are available if requested within 7 days of the payment date.\n② After 7 days, refunds are not available; only subscription cancellation is possible.\n③ Refund requests should be submitted via email (${CONTACT_EMAIL}).\n④ Refunds are processed within 7 business days of the request.`,
  },
  {
    title: "4. Non-Refundable Cases",
    content: `Refunds are not available in the following cases:\n• More than 7 days have passed since the payment date\n• The service has been substantially used\n• The account has been suspended due to Terms of Service violations\n• Simple change of mind (except within the 7-day period)`,
  },
  {
    title: "5. Plan Changes",
    content: `① Upgrading from Pro to Pro+ will result in an immediate prorated charge.\n② Downgrading from Pro+ to Pro takes effect after the current billing period ends.\n③ Plan changes can be made via Settings > Subscription Management.`,
  },
  {
    title: "6. Contact",
    content: `Refund inquiries: ${CONTACT_EMAIL}\nResponse time: within 1-3 business days`,
  },
];
