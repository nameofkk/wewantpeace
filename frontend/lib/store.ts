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
  showSpikesOnly: boolean;
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

  // 관심지역 (localStorage 저장)
  myCountries: string[];

  // 언어
  lang: Lang;

  // 테마
  theme: Theme;

  // 액션
  setMapViewport: (v: Partial<Viewport>) => void;
  setSelectedCluster: (id: string | null) => void;
  setFilter: (key: keyof FilterState, value: FilterState[keyof FilterState]) => void;
  setTrendingTab: (tab: "global" | "mine") => void;
  setUserPlan: (plan: "free" | "pro" | "pro_plus") => void;
  addMyCountry: (code: string, plan?: string) => boolean; // false = 제한 초과
  removeMyCountry: (code: string) => void;
  setLang: (lang: Lang) => void;
  setTheme: (theme: Theme) => void;
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
        showSpikesOnly: false,
      },
      userPlan: "free",
      trendingTab: "global",
      myCountries: [],
      lang: "ko",
      theme: "dark",

      setMapViewport: (v) =>
        set((state) => ({ mapViewport: { ...state.mapViewport, ...v } })),
      setSelectedCluster: (id) => set({ selectedClusterId: id }),
      setFilter: (key, value) =>
        set((state) => ({
          activeFilters: { ...state.activeFilters, [key]: value },
        })),
      setTrendingTab: (tab) => set({ trendingTab: tab }),
      setUserPlan: (plan) => set({ userPlan: plan }),

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
      setTheme: (theme) => {
        set({ theme });
        if (typeof document !== "undefined") {
          document.documentElement.classList.toggle("dark", theme === "dark");
          document.documentElement.classList.toggle("light", theme === "light");
        }
      },
    }),
    {
      name: "wwp-store",
      version: 4, // v1→v2: 기본 8개국 → 빈 배열, v3: lang, v4: theme
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
        return s;
      },
      partialize: (state) => ({
        myCountries: state.myCountries,
        trendingTab: state.trendingTab,
        userPlan: state.userPlan,
        lang: state.lang,
        theme: state.theme,
      }),
    }
  )
);

export { FREE_COUNTRY_LIMIT, PRO_COUNTRY_LIMIT };
