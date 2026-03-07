"use client";

import { initializeApp, getApps, FirebaseApp } from "firebase/app";
import {
  getAuth,
  Auth,
  GoogleAuthProvider,
  OAuthProvider,
  signInWithPopup,
  signInWithRedirect,
  getRedirectResult,
  signInWithCustomToken,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendPasswordResetEmail as firebaseSendPasswordResetEmail,
  signOut as firebaseSignOut,
  onIdTokenChanged,
  User as FirebaseUser,
} from "firebase/auth";
import { useState, useEffect, useCallback, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  measurementId: process.env.NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID,
};

// Firebase 설정 완료 여부 확인
const IS_FIREBASE_CONFIGURED =
  typeof firebaseConfig.apiKey === "string" && firebaseConfig.apiKey.length > 0;

let _app: FirebaseApp | null = null;
let _auth: Auth | null = null;

function getFirebaseAuth(): Auth | null {
  if (!IS_FIREBASE_CONFIGURED) return null;
  if (!_auth) {
    _app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0];
    _auth = getAuth(_app);
  }
  return _auth;
}

/** React Native WebView 환경인지 확인 */
function isReactNativeWebView(): boolean {
  return typeof window !== "undefined" && !!window.__REACT_NATIVE__;
}

// Google 로그인
export async function signInWithGoogle(): Promise<FirebaseUser> {
  const auth = getFirebaseAuth();
  if (!auth) {
    throw new Error(
      "Firebase가 설정되지 않았습니다. .env.local에 NEXT_PUBLIC_FIREBASE_API_KEY를 설정하세요."
    );
  }
  const provider = new GoogleAuthProvider();
  provider.setCustomParameters({ prompt: "select_account" });

  if (isReactNativeWebView()) {
    // React Native WebView: signInWithPopup은 같은 창에서 열려 빈 화면 발생
    // signInWithRedirect 사용 → 리다이렉트 후 getRedirectResult로 결과 확인
    await signInWithRedirect(auth, provider);
    // signInWithRedirect는 페이지를 리다이렉트하므로 여기에 도달하지 않음
    throw new Error("redirect");
  }

  // 웹 브라우저: signInWithPopup 사용 (정상 팝업)
  const result = await signInWithPopup(auth, provider);
  return result.user;
}

/**
 * Google 리다이렉트 로그인 결과 확인 (React Native WebView 전용).
 * 로그인 페이지 마운트 시 호출하여 리다이렉트 후 복귀한 경우 인증 결과를 처리.
 */
export async function checkGoogleRedirectResult(): Promise<FirebaseUser | null> {
  const auth = getFirebaseAuth();
  if (!auth) return null;
  try {
    // 3초 타임아웃 — 일부 브라우저(Whale 등)에서 getRedirectResult가 hang하는 문제 방지
    const result = await Promise.race([
      getRedirectResult(auth),
      new Promise<null>((resolve) => setTimeout(() => resolve(null), 3000)),
    ]);
    return result?.user ?? null;
  } catch {
    return null;
  }
}

// Apple 로그인
export async function signInWithApple(): Promise<FirebaseUser> {
  const auth = getFirebaseAuth();
  if (!auth) {
    throw new Error(
      "Firebase가 설정되지 않았습니다. .env.local에 NEXT_PUBLIC_FIREBASE_API_KEY를 설정하세요."
    );
  }
  const provider = new OAuthProvider("apple.com");
  provider.addScope("email");
  provider.addScope("name");

  if (isReactNativeWebView()) {
    // React Native WebView: signInWithPopup은 같은 창에서 열려 빈 화면 발생
    // signInWithRedirect 사용 → 리다이렉트 후 getRedirectResult로 결과 확인
    await signInWithRedirect(auth, provider);
    // signInWithRedirect는 페이지를 리다이렉트하므로 여기에 도달하지 않음
    throw new Error("redirect");
  }

  // 웹 브라우저: signInWithPopup 사용 (정상 팝업)
  const result = await signInWithPopup(auth, provider);
  return result.user;
}

// 카카오 로그인
export async function signInWithKakao(): Promise<void> {
  const kakaoAppKey = process.env.NEXT_PUBLIC_KAKAO_APP_KEY;
  if (!kakaoAppKey) {
    throw new Error("NEXT_PUBLIC_KAKAO_APP_KEY가 설정되지 않았습니다.");
  }
  const kakaoAuthUrl = `https://kauth.kakao.com/oauth/authorize?client_id=${kakaoAppKey}&redirect_uri=${encodeURIComponent(window.location.origin + "/api/auth/kakao/callback")}&response_type=code`;
  window.location.href = kakaoAuthUrl;
}

// 이메일 로그인
export async function signInWithEmail(email: string, password: string): Promise<FirebaseUser> {
  const auth = getFirebaseAuth();
  if (!auth) throw new Error("Firebase가 설정되지 않았습니다.");
  const result = await signInWithEmailAndPassword(auth, email, password);
  return result.user;
}

// 이메일 회원가입
export async function createEmailUser(email: string, password: string): Promise<FirebaseUser> {
  const auth = getFirebaseAuth();
  if (!auth) throw new Error("Firebase가 설정되지 않았습니다.");
  const result = await createUserWithEmailAndPassword(auth, email, password);
  return result.user;
}

// 토스 앱인토스 로그인
export async function signInWithToss(): Promise<{
  user: FirebaseUser | null;
  isNewUser: boolean;
}> {
  const { createAsyncBridge } = await import("@apps-in-toss/bridge-core");
  const appLogin = createAsyncBridge<
    [],
    { authorizationCode: string; referrer: string }
  >("appLogin");

  // 1. 토스 네이티브 로그인 → authorizationCode 획득
  const { authorizationCode } = await appLogin();

  // 2. 백엔드에서 코드 교환 → Firebase Custom Token
  const API_BASE =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
  const res = await fetch(`${API_BASE}/auth/toss-login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ authorization_code: authorizationCode }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(
      err.detail || "토스 로그인에 실패했습니다."
    );
  }

  const { firebase_custom_token, is_new_user } = await res.json();

  // 3. Firebase Custom Token으로 인증
  const auth = getFirebaseAuth();
  if (!auth) throw new Error("Firebase가 설정되지 않았습니다.");

  const result = await signInWithCustomToken(auth, firebase_custom_token);
  return { user: result.user, isNewUser: is_new_user };
}

// 비밀번호 재설정 이메일 발송
export async function sendPasswordResetEmail(email: string): Promise<void> {
  const auth = getFirebaseAuth();
  if (!auth) throw new Error("Firebase가 설정되지 않았습니다.");
  await firebaseSendPasswordResetEmail(auth, email);
}

// 로그아웃
export async function signOut(): Promise<void> {
  const auth = getFirebaseAuth();
  if (!auth) return;
  await firebaseSignOut(auth);
}

// Firebase ID Token 가져오기 (API 호출용)
export async function getIdToken(): Promise<string | null> {
  const auth = getFirebaseAuth();
  if (!auth) return null;
  const user = auth.currentUser;
  if (!user) return null;
  return user.getIdToken();
}

// useAuth hook
export function useAuth() {
  const [user, setUser] = useState<FirebaseUser | null>(null);
  const [loading, setLoading] = useState(IS_FIREBASE_CONFIGURED); // 미설정이면 즉시 false
  const queryClient = useQueryClient();
  const prevUid = useRef<string | null>(null);

  useEffect(() => {
    if (!IS_FIREBASE_CONFIGURED) {
      setLoading(false);
      return;
    }
    const auth = getFirebaseAuth();
    if (!auth) {
      setLoading(false);
      return;
    }
    const unsubscribe = onIdTokenChanged(auth, async (u) => {
      setUser(u);
      const uid = u?.uid ?? null;
      // Firebase SDK가 내부적으로 토큰을 관리하므로 localStorage 저장 불필요
      // 로그인/로그아웃 시 사용자 관련 캐시 즉시 무효화
      if (uid !== prevUid.current) {
        prevUid.current = uid;
        queryClient.invalidateQueries({ queryKey: ["me"] });
        queryClient.invalidateQueries({ queryKey: ["tension"] });
      }
      setLoading(false);
    });
    return () => unsubscribe();
  }, [queryClient]);

  const getToken = useCallback(async () => {
    if (!user) return null;
    return user.getIdToken();
  }, [user]);

  return { user, loading, getIdToken: getToken };
}

export { getFirebaseAuth };
