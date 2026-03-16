import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Lang } from "./i18n";

export type Theme = "dark" | "light";

interface Viewport {
  longitude: number;
  latitude: number;
  zoom: number;
}

interface FilterState {
  topics: string[];
  severityMin: number;
  showHighKScoreOnly: boolean;
}

const FREE_COUNTRY_LIMIT = 2;
const PRO_COUNTRY_LIMIT = 5;

interface AppStore {
  // 지도 상태
  mapViewport: Viewport;
  selectedClusterId: string | null;
  activeFilters: FilterState;

  // 사용자 상태
  userPlan: "free" | "pro" | "pro_plus";

  // 트렌딩 탭
  trendingTab: "global" | "mine";

  // 관심 국가 (localStorage 저장)
  myCountries: string[];

  // 언어
  lang: Lang;

  // 테마
  theme: Theme;

  // 내 국가 (KScore 개인화)
  homeCountry: string;

  // 놓친 알림 카운트 (구독 전환 유도)
  missedAlertCount: number;
  missedAlertDismissedAt: number | null; // timestamp
  incrementMissedAlertCount: () => void;
  dismissUpgradeNudge: () => void;

  // 가이드 투어
  completedTours: string[];
  markTourComplete: (tour: string) => void;
  resetTour: (tour: string) => void;

  // 액션
  setMapViewport: (v: Partial<Viewport>) => void;
  setSelectedCluster: (id: string | null) => void;
  setFilter: (key: keyof FilterState, value: FilterState[keyof FilterState]) => void;
  setTrendingTab: (tab: "global" | "mine") => void;
  setUserPlan: (plan: "free" | "pro" | "pro_plus") => void;
  setMyCountries: (codes: string[]) => void;
  addMyCountry: (code: string, plan?: string) => boolean; // false = 제한 초과
  removeMyCountry: (code: string) => void;
  setLang: (lang: Lang) => void;
  setTheme: (theme: Theme) => void;
  setHomeCountry: (code: string) => void;
  reset: () => void;
}

export const useAppStore = create<AppStore>()(
  persist(
    (set, get) => ({
      mapViewport: {
        longitude: 20,
        latitude: 30,
        zoom: 1.5,
      },
      selectedClusterId: null,
      activeFilters: {
        topics: ["conflict", "terror", "coup", "sanctions", "cyber", "protest"],
        severityMin: 35,
        showHighKScoreOnly: false,
      },
      userPlan: "free",
      trendingTab: "global",
      myCountries: [],
      lang: "en",
      theme: "dark",
      homeCountry: "",
      missedAlertCount: 0,
      missedAlertDismissedAt: null,
      incrementMissedAlertCount: () =>
        set((state) => ({ missedAlertCount: state.missedAlertCount + 1 })),
      dismissUpgradeNudge: () =>
        set({ missedAlertDismissedAt: Date.now() }),

      completedTours: [],
      markTourComplete: (tour) =>
        set((state) => ({
          completedTours: state.completedTours.includes(tour)
            ? state.completedTours
            : [...state.completedTours, tour],
        })),
      resetTour: (tour) =>
        set((state) => ({
          completedTours: state.completedTours.filter((t) => t !== tour),
        })),

      setMapViewport: (v) =>
        set((state) => ({ mapViewport: { ...state.mapViewport, ...v } })),
      setSelectedCluster: (id) => set({ selectedClusterId: id }),
      setFilter: (key, value) =>
        set((state) => ({
          activeFilters: { ...state.activeFilters, [key]: value },
        })),
      setTrendingTab: (tab) => set({ trendingTab: tab }),
      setUserPlan: (plan) => set({ userPlan: plan }),

      setMyCountries: (codes) => set({ myCountries: codes }),
      addMyCountry: (code, planOverride) => {
        const { myCountries, userPlan } = get();
        const effectivePlan = planOverride ?? userPlan;
        if (myCountries.includes(code)) return true;
        if (effectivePlan === "free" && myCountries.length >= FREE_COUNTRY_LIMIT) return false;
        if (effectivePlan === "pro" && myCountries.length >= PRO_COUNTRY_LIMIT) return false;
        set({ myCountries: [...myCountries, code] });
        return true;
      },
      removeMyCountry: (code) =>
        set((state) => ({ myCountries: state.myCountries.filter((c) => c !== code) })),
      setLang: (lang) => set({ lang }),
      setHomeCountry: (code) => set({ homeCountry: code }),
      setTheme: (theme) => {
        set({ theme });
        if (typeof document !== "undefined") {
          document.documentElement.classList.toggle("dark", theme === "dark");
          document.documentElement.classList.toggle("light", theme === "light");
        }
      },
      reset: () => {
        set({
          myCountries: [],
          homeCountry: "",
          userPlan: "free",
          completedTours: [],
          missedAlertCount: 0,
          missedAlertDismissedAt: null,
          trendingTab: "global",
          selectedClusterId: null,
        });
        // persist 스토리지도 클리어
        if (typeof window !== "undefined") {
          try { localStorage.removeItem("wwp-store"); } catch {}
        }
      },
    }),
    {
      name: "wwp-store",
      version: 9, // v1→v2: 기본 8개국 → 빈 배열, v3: lang, v4: theme, v5: homeCountry, v6: completedTours, v7: spikeAlertCount, v8: missedAlertCount, v9: global defaults (lang=en, homeCountry="")
      migrate: (old: unknown, version: number) => {
        const s = old as Record<string, unknown>;
        if (version < 2) {
          return { ...s, myCountries: [] };
        }
        if (version < 3) {
          return { ...s, lang: "ko" };
        }
        if (version < 4) {
          return { ...s, theme: "dark" };
        }
        if (version < 5) {
          return { ...s, homeCountry: "KR" };
        }
        if (version < 6) {
          return { ...s, completedTours: [] };
        }
        if (version < 7) {
          return { ...s, spikeAlertCount: 0, spikeAlertDismissedAt: null };
        }
        if (version < 8) {
          // Migrate spikeAlertCount → missedAlertCount
          return {
            ...s,
            missedAlertCount: (s as Record<string, unknown>).spikeAlertCount ?? 0,
            missedAlertDismissedAt: (s as Record<string, unknown>).spikeAlertDismissedAt ?? null,
          };
        }
        if (version < 9) {
          // v9: 기존 유저는 설정 유지 (이미 개인화한 값이므로 변경하지 않음)
          return s;
        }
        return s;
      },
      partialize: (state) => ({
        myCountries: state.myCountries,
        trendingTab: state.trendingTab,
        userPlan: state.userPlan,
        lang: state.lang,
        theme: state.theme,
        homeCountry: state.homeCountry,
        completedTours: state.completedTours,
        missedAlertCount: state.missedAlertCount,
        missedAlertDismissedAt: state.missedAlertDismissedAt,
      }),
    }
  )
);

export { FREE_COUNTRY_LIMIT, PRO_COUNTRY_LIMIT };
