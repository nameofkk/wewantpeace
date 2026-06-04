# 커뮤니티 UI/UX 리디자인 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 커뮤니티를 토스/카카오 스타일의 모던 UI로 개편하고 북마크, 검색, 무한스크롤, 마크다운 에디터 기능 추가.

**Architecture:** 프론트엔드 비주얼 리디자인 + 백엔드 API 확장(북마크 모델/엔드포인트, 검색 쿼리, 커서 페이지네이션). 프론트엔드는 기존 페이지 파일을 직접 수정하며, 새 컴포넌트는 `components/community/`에 추가.

**Tech Stack:** Next.js 14, React 18, Tailwind CSS, framer-motion (이미 설치됨), React Query (useInfiniteQuery), FastAPI, SQLAlchemy, PostgreSQL.

---

## Phase 1: 백엔드 API 확장

### Task 1: 북마크 모델 & 마이그레이션

**Files:**
- Modify: `backend/app/models/community.py` — Bookmark 모델 추가
- Create: `backend/alembic/versions/0038_bookmarks.py` — 마이그레이션

**Step 1: Bookmark 모델 추가**

`backend/app/models/community.py` 맨 아래에 추가:

```python
class Bookmark(Base):
    __tablename__ = "bookmarks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("user_id", "post_id", name="uq_bookmark_user_post"),)
```

**Step 2: 마이그레이션 생성 & 적용**

```bash
cd ~/Projects/wewantpeace
.venv/bin/alembic revision --autogenerate -m "add bookmarks table"
DATABASE_URL="postgresql+asyncpg://postgres.smxitufpgfuzepldglfo:WwpAdmin2026@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres" .venv/bin/alembic upgrade head
```

**Step 3: Commit**

```bash
git add backend/app/models/community.py backend/alembic/versions/
git commit -m "feat(community): add bookmarks model & migration"
```

---

### Task 2: 북마크 API 엔드포인트

**Files:**
- Modify: `backend/app/routers/community.py` — 북마크 토글 + 목록 엔드포인트

**Step 1: 북마크 토글 엔드포인트 추가**

`community.py` 라우터에 추가:

```python
from backend.app.models.community import Bookmark

@router.post("/posts/{post_id}/bookmark")
async def toggle_bookmark(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """북마크 토글 — 이미 있으면 삭제, 없으면 추가."""
    uid = uuid.UUID(post_id)
    result = await db.execute(
        select(Bookmark).where(Bookmark.user_id == current_user.id, Bookmark.post_id == uid)
    )
    existing = result.scalar_one_or_none()
    if existing:
        await db.delete(existing)
        await db.flush()
        return {"bookmarked": False}
    db.add(Bookmark(user_id=current_user.id, post_id=uid))
    await db.flush()
    return {"bookmarked": True}
```

**Step 2: 내 북마크 목록 엔드포인트**

```python
@router.get("/bookmarks", response_model=list[PostOut])
async def list_bookmarks(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내 북마크 목록."""
    q = (
        select(Post)
        .join(Bookmark, Bookmark.post_id == Post.id)
        .where(Bookmark.user_id == current_user.id, Post.status == "active")
        .order_by(Bookmark.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    rows = (await db.execute(q)).scalars().all()
    return [_post_to_out(p) for p in rows]
```

**Step 3: PostOut에 is_bookmarked 필드 추가**

`PostOut` 스키마에 `is_bookmarked: bool = False` 필드 추가.
`list_posts`, `get_post`에서 로그인 사용자면 북마크 여부를 조회해서 세팅.

**Step 4: Commit**

```bash
git add backend/app/routers/community.py
git commit -m "feat(community): add bookmark toggle & list endpoints"
```

---

### Task 3: 검색 쿼리 파라미터 추가

**Files:**
- Modify: `backend/app/routers/community.py` — `list_posts`에 `q` 파라미터

**Step 1: q 파라미터 추가**

`list_posts` 함수에 `q: Optional[str] = Query(None, min_length=2, max_length=100)` 추가.

필터 로직:
```python
if q:
    q_filter = f"%{q}%"
    query = query.where(
        or_(Post.title.ilike(q_filter), Post.content.ilike(q_filter))
    )
```

**Step 2: Commit**

```bash
git add backend/app/routers/community.py
git commit -m "feat(community): add search query parameter to list_posts"
```

---

### Task 4: 커서 기반 페이지네이션 지원

**Files:**
- Modify: `backend/app/routers/community.py` — cursor 파라미터 추가

**Step 1: list_posts에 cursor 파라미터 추가**

기존 page/limit 유지하면서 cursor도 지원:

```python
cursor: Optional[str] = Query(None, description="마지막 게시글 ID (무한스크롤용)")
```

cursor가 있으면:
```python
if cursor:
    cursor_post = await db.get(Post, uuid.UUID(cursor))
    if cursor_post:
        if sort_by == "popular":
            score = cursor_post.view_count + cursor_post.like_count
            query = query.where(
                or_(
                    (Post.view_count + Post.like_count) < score,
                    and_(
                        (Post.view_count + Post.like_count) == score,
                        Post.created_at < cursor_post.created_at,
                    ),
                )
            )
        else:
            query = query.where(Post.created_at < cursor_post.created_at)
```

**Step 2: 응답에 next_cursor 추가**

리스트 응답 래퍼:
```python
return {"posts": posts_out, "next_cursor": posts_out[-1].id if len(posts_out) == limit else None}
```

**Step 3: Commit**

```bash
git add backend/app/routers/community.py
git commit -m "feat(community): add cursor-based pagination for infinite scroll"
```

---

### Task 5: 백엔드 배포

```bash
cd ~/Projects/wewantpeace
RAILWAY_API_TOKEN=383ab19c-f63d-4ad0-ae47-ef816b79645b /home/krshin7/.npm-global/bin/railway up --service backend --detach
```

---

## Phase 2: 프론트엔드 — 공통 컴포넌트

### Task 6: 아바타 컴포넌트

**Files:**
- Create: `frontend/components/community/Avatar.tsx`

닉네임 첫 글자로 원형 아바타. Pro/Pro+ 배지 포함.

```tsx
interface AvatarProps {
  nickname: string | null;
  plan?: string | null;
  size?: "sm" | "md";
}
```

- sm: `w-8 h-8 text-xs`
- md: `w-10 h-10 text-sm`
- 배경색: 닉네임 해시 기반 파스텔 색상 6가지 중 선택
- Pro 배지: 아바타 우하단 작은 원형 (`w-3.5 h-3.5`)

**Commit:** `feat(community): add Avatar component`

---

### Task 7: 마크다운 파서 & 렌더러

**Files:**
- Create: `frontend/lib/markdown.ts` — 경량 마크다운 파서
- Create: `frontend/components/community/MarkdownContent.tsx` — 렌더링 컴포넌트

정규식 기반 파서 (외부 라이브러리 없이):
- `**bold**` → `<strong>`
- `*italic*` → `<em>`
- `[text](url)` → `<a>`
- `> quote` → `<blockquote>`
- `- item` → `<li>`
- 줄바꿈 → `<br>`

**Commit:** `feat(community): add lightweight markdown parser & renderer`

---

### Task 8: 마크다운 에디터 툴바

**Files:**
- Create: `frontend/components/community/MarkdownToolbar.tsx`

버튼 5개: B (볼드), I (이탤릭), 링크, 인용, 리스트.
각 버튼은 textarea에 마크다운 구문 삽입.

**Commit:** `feat(community): add markdown editor toolbar`

---

## Phase 3: 프론트엔드 — 메인 리스트 리디자인

### Task 9: API 함수 업데이트

**Files:**
- Modify: `frontend/lib/api.ts` — 새 API 함수 추가

```typescript
// 무한 스크롤용
export async function fetchPostsCursor(params: {
  cursor?: string; limit?: number; post_type?: string; sort_by?: string; q?: string;
}): Promise<{ posts: Post[]; next_cursor: string | null }>;

// 북마크 토글
export async function toggleBookmark(postId: string): Promise<{ bookmarked: boolean }>;

// 내 북마크 목록
export async function fetchBookmarks(page?: number): Promise<Post[]>;
```

**Commit:** `feat(community): add API functions for cursor pagination, bookmarks, search`

---

### Task 10: 메인 커뮤니티 페이지 리디자인

**Files:**
- Modify: `frontend/app/(main)/community/page.tsx` — 전체 리디자인

핵심 변경:
1. **검색바**: 상단 pill 형태 input, 디바운스 300ms
2. **필터 칩**: 탭 → pill 버튼 (`rounded-full`, gap-2, 수평 스크롤)
3. **핫토픽**: 카드형 `rounded-2xl shadow-sm` 수평 캐러셀
4. **게시글 카드 리디자인**:
   - 아바타(Avatar) + 닉네임/시간 한 줄
   - 제목 (font-semibold)
   - 본문 미리보기 2줄 (`line-clamp-2 text-muted-foreground text-sm`)
   - 이미지 있으면 우측 `w-14 h-14 rounded-xl` 썸네일
   - 하단: 좋아요/댓글/조회수/북마크 아이콘
   - 카드: `rounded-2xl` + `divide-y divide-border` (카드 분리선)
5. **무한 스크롤**: `useInfiniteQuery` + IntersectionObserver
6. **글쓰기 FAB**: 우하단 플로팅 버튼 (`fixed bottom-20 right-4`)
7. **framer-motion**: 리스트 stagger 애니메이션

**Commit:** `feat(community): redesign main list page with modern UI`

---

### Task 11: 게시글 상세 페이지 리디자인

**Files:**
- Modify: `frontend/app/(main)/community/[postId]/client.tsx`

핵심 변경:
1. 작성자 영역: 아바타(md) + 닉네임 + 시간 + 타입 배지
2. 본문: `MarkdownContent` 컴포넌트로 렌더링
3. 이미지: 본문 아래 자연스러운 그리드 (기존 유지, 둥근 모서리 강화)
4. 댓글 영역: 배경 분리 (`bg-muted/20 rounded-t-2xl`)
5. 댓글 아이템: 아바타(sm) + 닉네임 + 내용
6. 북마크 버튼 추가 (상단 헤더 또는 반응 영역)

**Commit:** `feat(community): redesign post detail page`

---

### Task 12: 글쓰기 페이지 업데이트

**Files:**
- Modify: `frontend/app/(main)/community/new/page.tsx`

핵심 변경:
1. 마크다운 툴바 추가 (MarkdownToolbar 컴포넌트)
2. 미리보기 토글 버튼 추가
3. 미리보기 모드에서 MarkdownContent 렌더링
4. 필터 칩 스타일 타입 선택 (기존 버튼 → pill 형태)

**Commit:** `feat(community): add markdown toolbar & preview to new post page`

---

## Phase 4: i18n & 마무리

### Task 13: i18n 문자열 추가

**Files:**
- Modify: `frontend/lib/i18n.ts` — ko/en 동시 추가

새 키:
- `community_search_placeholder`: "게시글 검색..." / "Search posts..."
- `community_bookmark`: "북마크" / "Bookmark"
- `community_bookmarked`: "북마크됨" / "Bookmarked"
- `community_bookmarks_title`: "저장한 글" / "Saved Posts"
- `community_bookmarks_empty`: "저장한 글이 없습니다" / "No saved posts"
- `community_write`: "글쓰기" / "Write"
- `community_preview`: "미리보기" / "Preview"
- `community_edit_mode`: "편집" / "Edit"
- `community_no_more`: "더 이상 게시글이 없습니다" / "No more posts"
- `community_loading_more`: "불러오는 중..." / "Loading..."

**Commit:** `feat(community): add i18n strings for new features`

---

### Task 14: 내 북마크 페이지

**Files:**
- Create: `frontend/app/(main)/community/bookmarks/page.tsx`

설정 페이지에서 접근 가능한 북마크 목록 페이지. 메인 리스트와 동일한 카드 디자인 사용.

**Commit:** `feat(community): add bookmarks page`

---

### Task 15: 최종 빌드 & 배포

1. 프론트엔드 빌드 확인
2. 토스 .ait 빌드
3. Railway 프론트엔드 배포
4. Git push

```bash
cd ~/Projects/wewantpeace/frontend && npm run build
cd ~/Projects/wewantpeace/frontend && sh build-toss.sh
# Railway frontend 배포
# Git push
```
