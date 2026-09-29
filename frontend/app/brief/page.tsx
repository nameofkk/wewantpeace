"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { API_BASE } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { trackEvent } from "@/lib/analytics";

// 나라별 주간 브리프 구독 (로그인 없음, 이중 확인). 2026-09-30 검증 실험용.
const COUNTRIES: { code: string; en: string; ko: string }[] = [
  { code: "UA", en: "Ukraine", ko: "우크라이나" },
  { code: "RU", en: "Russia", ko: "러시아" },
  { code: "IL", en: "Israel", ko: "이스라엘" },
  { code: "PS", en: "Palestine", ko: "팔레스타인" },
  { code: "LB", en: "Lebanon", ko: "레바논" },
  { code: "IR", en: "Iran", ko: "이란" },
  { code: "SY", en: "Syria", ko: "시리아" },
  { code: "YE", en: "Yemen", ko: "예멘" },
  { code: "IQ", en: "Iraq", ko: "이라크" },
  { code: "SD", en: "Sudan", ko: "수단" },
  { code: "TW", en: "Taiwan", ko: "대만" },
  { code: "CN", en: "China", ko: "중국" },
  { code: "KP", en: "North Korea", ko: "북한" },
  { code: "KR", en: "South Korea", ko: "한국" },
  { code: "PK", en: "Pakistan", ko: "파키스탄" },
  { code: "IN", en: "India", ko: "인도" },
  { code: "MM", en: "Myanmar", ko: "미얀마" },
  { code: "ET", en: "Ethiopia", ko: "에티오피아" },
  { code: "VE", en: "Venezuela", ko: "베네수엘라" },
  { code: "TR", en: "Turkey", ko: "튀르키예" },
];
const MAX = 3;

const TEXT = {
  en: {
    kicker: "Weekly country brief",
    title: "One calm email a week about the countries you follow",
    lead: "What happened, why it matters and what to watch, with the number of independent sources behind each point. No live alerts, no dashboards.",
    pick: `Pick up to ${MAX} countries`,
    email: "Email",
    consent: "I agree that WeWantPeace may use my email address and chosen countries to send this brief. I can unsubscribe from any email.",
    privacy: "Privacy policy",
    submit: "Send me the brief",
    sending: "Sending…",
    sent_title: "Check your inbox",
    sent_body: "We sent a confirmation link. Nothing is sent until you click it.",
    err_email: "Please enter a valid email address.",
    err_pick: "Pick at least one country.",
    err_consent: "Please tick the consent box.",
    err_generic: "Something went wrong. Please try again in a minute.",
    sample: "What a brief looks like",
    sample_body: "Ethiopia. Federal forces and allied militias are clashing with a new alliance of armed opposition groups across Tigray, Amhara and Afar. Why it matters: a return to large-scale fighting in the north, with Ethiopia accusing Sudan and Egypt of backing the rebels. What to watch: whether the counteroffensive holds, and any move by Egypt or Sudan. 6 independent sources.",
  },
  ko: {
    kicker: "나라별 주간 브리프",
    title: "관심 있는 나라 소식을 일주일에 한 번, 차분하게",
    lead: "무슨 일이 있었고, 왜 중요하고, 무엇을 지켜봐야 하는지. 항목마다 독립 출처가 몇 곳인지 함께 적습니다. 실시간 알림도 대시보드도 없습니다.",
    pick: `나라를 최대 ${MAX}곳 고르세요`,
    email: "이메일",
    consent: "브리프 발송을 위해 이메일 주소와 선택한 나라를 이용하는 데 동의합니다. 모든 메일에서 언제든 수신거부할 수 있습니다.",
    privacy: "개인정보처리방침",
    submit: "브리프 받기",
    sending: "보내는 중…",
    sent_title: "메일함을 확인해 주세요",
    sent_body: "확인 링크를 보냈습니다. 링크를 누르기 전에는 아무것도 보내지 않습니다.",
    err_email: "올바른 이메일 주소를 입력해 주세요.",
    err_pick: "나라를 한 곳 이상 골라 주세요.",
    err_consent: "동의에 체크해 주세요.",
    err_generic: "문제가 생겼습니다. 잠시 뒤 다시 시도해 주세요.",
    sample: "브리프 예시",
    sample_body: "에티오피아. 연방군과 동맹 민병대가 티그라이·암하라·아파르에서 새로 결성된 반군 연합과 교전 중. 왜 중요한가: 북부 대규모 전투 재개, 에티오피아는 수단·이집트의 반군 지원을 주장. 지켜볼 점: 반격 지속 여부와 이집트·수단의 움직임. 독립 출처 6곳.",
  },
} as const;

export default function BriefSubscribePage() {
  const storeLang = useAppStore((s) => s.lang);
  const [lang, setLang] = useState<"en" | "ko">("en");
  const [picked, setPicked] = useState<string[]>([]);
  const [email, setEmail] = useState("");
  const [consent, setConsent] = useState(false);
  const [state, setState] = useState<"idle" | "sending" | "sent">("idle");
  const [error, setError] = useState("");

  useEffect(() => {
    setLang(storeLang === "ko" ? "ko" : "en");
    // ?c=UA 로 들어오면 미리 골라 둔다 (나라 페이지·스레드 링크용)
    const cc = new URLSearchParams(window.location.search).get("c")?.toUpperCase();
    if (cc && COUNTRIES.some((c) => c.code === cc)) setPicked([cc]);
  }, [storeLang]);

  const T = TEXT[lang];

  function toggle(code: string) {
    setPicked((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : prev.length >= MAX ? prev : [...prev, code],
    );
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!/^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/.test(email.trim())) return setError(T.err_email);
    if (picked.length === 0) return setError(T.err_pick);
    if (!consent) return setError(T.err_consent);
    setState("sending");
    const params = new URLSearchParams(window.location.search);
    try {
      const res = await fetch(`${API_BASE}/briefs/subscribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          countries: picked,
          lang,
          consent,
          source: params.get("ref") || params.get("utm_source") || null,
        }),
      });
      if (!res.ok) throw new Error(String(res.status));
      setState("sent");
      trackEvent("brief_subscribe", { countries: picked.join(","), lang });
    } catch {
      setState("idle");
      setError(T.err_generic);
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-xl px-4 py-10">
        <div className="flex items-center justify-between mb-8">
          <Link href="/" className="text-sm font-semibold tracking-tight">WeWantPeace</Link>
          <div className="flex gap-1 text-xs">
            {(["en", "ko"] as const).map((l) => (
              <button
                key={l}
                type="button"
                onClick={() => setLang(l)}
                className={`rounded px-2 py-1 ${lang === l ? "bg-secondary text-foreground" : "text-muted-foreground"}`}
              >
                {l === "en" ? "English" : "한국어"}
              </button>
            ))}
          </div>
        </div>

        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary mb-3">{T.kicker}</p>
        <h1 className="text-2xl sm:text-3xl font-bold leading-tight mb-3" style={{ textWrap: "balance" }}>{T.title}</h1>
        <p className="text-sm text-muted-foreground leading-relaxed mb-8">{T.lead}</p>

        {state === "sent" ? (
          <div className="rounded-xl border border-border bg-card p-6">
            <h2 className="text-lg font-semibold mb-2">{T.sent_title}</h2>
            <p className="text-sm text-muted-foreground">{T.sent_body}</p>
          </div>
        ) : (
          <form onSubmit={onSubmit} method="post" className="space-y-6" noValidate>
            <fieldset>
              <legend className="text-sm font-medium mb-3">
                {T.pick} <span className="text-muted-foreground">({picked.length}/{MAX})</span>
              </legend>
              <div className="flex flex-wrap gap-2">
                {COUNTRIES.map((c) => {
                  const on = picked.includes(c.code);
                  const full = !on && picked.length >= MAX;
                  return (
                    <button
                      key={c.code}
                      type="button"
                      aria-pressed={on}
                      disabled={full}
                      onClick={() => toggle(c.code)}
                      className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
                        on
                          ? "border-primary bg-primary/15 text-foreground"
                          : "border-border text-muted-foreground hover:text-foreground disabled:opacity-40"
                      }`}
                    >
                      {lang === "ko" ? c.ko : c.en}
                    </button>
                  );
                })}
              </div>
            </fieldset>

            <label className="block">
              <span className="text-sm font-medium">{T.email}</span>
              <input
                type="email"
                name="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-2 w-full rounded-lg border border-border bg-card px-3 py-2.5 text-sm outline-none focus:border-primary"
                placeholder="you@example.com"
              />
            </label>

            <label className="flex items-start gap-3 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                className="mt-0.5 h-4 w-4 shrink-0 accent-[hsl(var(--primary))]"
              />
              <span>
                {T.consent}{" "}
                <Link href="/privacy" className="underline underline-offset-2 hover:text-foreground">{T.privacy}</Link>
              </span>
            </label>

            {error && <p role="alert" className="text-sm text-red-400">{error}</p>}

            <button
              type="submit"
              disabled={state === "sending"}
              className="w-full rounded-lg bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
            >
              {state === "sending" ? T.sending : T.submit}
            </button>
          </form>
        )}

        <div className="mt-10 border-t border-border pt-6">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground mb-2">{T.sample}</p>
          <p className="text-sm leading-relaxed text-muted-foreground">{T.sample_body}</p>
        </div>
      </div>
    </div>
  );
}
