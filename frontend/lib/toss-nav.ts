import { isTossMiniApp } from "./platform";

/**
 * 토스 미니앱에서 동적 라우트를 정적 뷰어 페이지로 리다이렉트하는 유틸리티.
 * 토스 빌드에서는 [id], [code], [postId] 동적 라우트가 비활성화되므로
 * 쿼리 파라미터 기반 정적 페이지로 네비게이션해야 합니다.
 */

/** 이슈 상세 페이지 경로 반환 */
export function issueDetailPath(id: string): string {
  if (isTossMiniApp()) return `/issues/view?id=${id}`;
  return `/issues/${id}`;
}

/** 국가별 이슈 페이지 경로 반환 */
export function countryIssuesPath(code: string): string {
  if (isTossMiniApp()) return `/issues/country-view?code=${code}`;
  return `/issues/country/${code}`;
}

/** 커뮤니티 글 상세 페이지 경로 반환 */
export function communityPostPath(postId: string | number): string {
  if (isTossMiniApp()) return `/community/post-view?id=${postId}`;
  return `/community/${postId}`;
}

/** 커뮤니티 글 수정 페이지 경로 반환 */
export function communityEditPath(postId: string | number): string {
  if (isTossMiniApp()) return `/community/post-view?id=${postId}&edit=1`;
  return `/community/${postId}/edit`;
}
