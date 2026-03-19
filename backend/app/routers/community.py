"""
/community/* 커뮤니티 API
"""
from __future__ import annotations
import asyncio
import os
import uuid
from datetime import datetime, date, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import get_current_user, get_optional_user, get_db
from backend.app.core.config import settings
from backend.app.core.limiter import limiter
from backend.app.models.user import User
from backend.app.models.community import Post, Comment, CommentReaction, PostReaction, Report, Bookmark
from backend.app.models.issue_cluster import IssueCluster

router = APIRouter(prefix="/community", tags=["community"])


def _translate_to_en_sync(text: str) -> str | None:
    """동기 번역 (스레드풀에서 실행)."""
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source="ko", target="en").translate(text[:5000])
    except Exception:
        return None


async def _translate_to_en(text: str) -> str | None:
    """비동기 번역 — 별도 스레드 + 10초 타임아웃."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_translate_to_en_sync, text),
            timeout=10.0,
        )
    except (asyncio.TimeoutError, Exception):
        return None

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB

# 매직바이트 → MIME 타입 매핑
_MAGIC_SIGNATURES = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"RIFF", "image/webp"),  # RIFF....WEBP
]


def _detect_image_type(data: bytes) -> str | None:
    """매직바이트로 이미지 MIME 타입 감지."""
    for sig, mime in _MAGIC_SIGNATURES:
        if data[:len(sig)] == sig:
            if mime == "image/webp" and data[8:12] != b"WEBP":
                continue
            return mime
    return None


# ── 스키마 ───────────────────────────────────────────────────────────────────

class PostCreate(BaseModel):
    title: str
    content: str
    post_type: str = "discussion"
    cluster_id: Optional[str] = None
    images: list[str] = []


class PostOut(BaseModel):
    id: str
    user_id: Optional[str]
    cluster_id: Optional[str]
    cluster_title: Optional[str] = None      # English title
    cluster_title_ko: Optional[str] = None   # Korean title
    title: str
    content: str
    title_en: Optional[str] = None
    content_en: Optional[str] = None
    post_type: str
    status: str
    view_count: int
    comment_count: int
    like_count: int
    dislike_count: int
    is_pinned: bool = False
    is_bookmarked: bool = False
    images: list[str]
    created_at: str
    updated_at: str
    author_nickname: Optional[str] = None
    author_plan: Optional[str] = None


class CommentCreate(BaseModel):
    content: str
    parent_id: Optional[str] = None


class CommentOut(BaseModel):
    id: str
    post_id: str
    user_id: Optional[str]
    parent_id: Optional[str]
    content: str
    content_en: Optional[str] = None
    status: str
    like_count: int
    created_at: str
    author_nickname: Optional[str] = None
    replies: list["CommentOut"] = []


class ReactionBody(BaseModel):
    reaction_type: str  # like | dislike


class ReportCreate(BaseModel):
    target_type: str
    target_id: str
    reason: str


def _post_to_out(
    p: Post,
    nickname: Optional[str] = None,
    cluster_title: Optional[str] = None,
    author_plan: Optional[str] = None,
    cluster_title_ko: Optional[str] = None,
    is_bookmarked: bool = False,
) -> PostOut:
    imgs: list[str] = []
    if p.images:
        if isinstance(p.images, list):
            imgs = p.images
        elif isinstance(p.images, dict):
            imgs = p.images.get("urls", [])
    return PostOut(
        id=str(p.id),
        user_id=str(p.user_id) if p.user_id else None,
        cluster_id=str(p.cluster_id) if p.cluster_id else None,
        cluster_title=cluster_title,
        cluster_title_ko=cluster_title_ko,
        title=p.title,
        content=p.content,
        title_en=p.title_en,
        content_en=p.content_en,
        post_type=p.post_type,
        status=p.status,
        view_count=p.view_count,
        comment_count=p.comment_count,
        like_count=p.like_count,
        dislike_count=p.dislike_count,
        is_pinned=p.is_pinned,
        is_bookmarked=is_bookmarked,
        images=imgs,
        created_at=p.created_at.isoformat(),
        updated_at=p.updated_at.isoformat(),
        author_nickname=nickname,
        author_plan=author_plan,
    )


def _comment_to_out(c: Comment, nickname: Optional[str] = None) -> CommentOut:
    return CommentOut(
        id=str(c.id),
        post_id=str(c.post_id),
        user_id=str(c.user_id) if c.user_id else None,
        parent_id=str(c.parent_id) if c.parent_id else None,
        content=c.content if c.status == "active" else "[삭제된 댓글입니다]",
        content_en=c.content_en if c.status == "active" else "[Deleted comment]",
        status=c.status,
        like_count=c.like_count,
        created_at=c.created_at.isoformat(),
        author_nickname=nickname,
    )


# ── 이미지 업로드 ──────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(422, detail="jpg/png/gif/webp 파일만 업로드 가능합니다.")

    contents = await file.read()
    if len(contents) > MAX_IMAGE_SIZE:
        raise HTTPException(422, detail="파일 크기는 5MB를 초과할 수 없습니다.")

    # 매직바이트 검증
    detected = _detect_image_type(contents)
    if detected not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(422, detail="파일 내용이 허용된 이미지 형식이 아닙니다.")

    # 확장자 화이트리스트
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        ext = detected.split("/")[-1]  # MIME에서 추출 (jpeg, png, gif, webp)

    filename = f"{uuid.uuid4()}.{ext}"
    filepath = os.path.join(settings.upload_dir, filename)

    os.makedirs(settings.upload_dir, exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(contents)

    url = f"/media/uploads/{filename}"
    return {"url": url}


# ── 게시글 ────────────────────────────────────────────────────────────────────

@router.get("/pinned-notices", response_model=list[PostOut])
async def pinned_notices(
    db: AsyncSession = Depends(get_db),
):
    """상단고정 공지사항 (최대 5개)"""
    q = (
        select(Post)
        .where(Post.status == "active", Post.post_type == "notice", Post.is_pinned == True)  # noqa: E712
        .order_by(Post.created_at.desc())
        .limit(5)
    )
    result = await db.execute(q)
    posts = result.scalars().all()

    user_ids = [p.user_id for p in posts if p.user_id]
    nicknames: dict[str, str] = {}
    plans: dict[str, str] = {}
    if user_ids:
        ur = await db.execute(select(User.id, User.nickname, User.plan).where(User.id.in_(user_ids)))
        for row in ur.fetchall():
            nicknames[str(row[0])] = row[1] or "관리자"
            plans[str(row[0])] = row[2]

    return [
        _post_to_out(p, nicknames.get(str(p.user_id)), None, plans.get(str(p.user_id)))
        for p in posts
    ]


@router.get("/posts")
async def list_posts(
    cluster_id: Optional[str] = Query(None),
    topic: Optional[str] = Query(None),
    post_type: Optional[str] = Query(None),
    sort_by: str = Query("latest"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    q: Optional[str] = Query(None, min_length=2, max_length=100),
    cursor: Optional[str] = Query(None, description="Last post ID for infinite scroll"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    query = select(Post).where(Post.status == "active")
    if cluster_id:
        try:
            query = query.where(Post.cluster_id == uuid.UUID(cluster_id))
        except ValueError:
            pass
    if post_type:
        query = query.where(Post.post_type == post_type)

    # 검색 필터
    if q:
        search_filter = f"%{q}%"
        query = query.where(or_(Post.title.ilike(search_filter), Post.content.ilike(search_filter)))

    # 커서 기반 페이지네이션
    if cursor:
        try:
            cursor_uuid = uuid.UUID(cursor)
            cursor_result = await db.execute(select(Post.created_at, Post.like_count, Post.view_count).where(Post.id == cursor_uuid))
            cursor_row = cursor_result.one_or_none()
            if cursor_row:
                if sort_by == "popular":
                    cursor_score = cursor_row[1] + cursor_row[2]  # like_count + view_count
                    query = query.where(
                        or_(
                            (Post.like_count + Post.view_count) < cursor_score,
                            ((Post.like_count + Post.view_count) == cursor_score) & (Post.created_at < cursor_row[0]),
                        )
                    )
                else:
                    query = query.where(Post.created_at < cursor_row[0])
        except ValueError:
            pass

    if sort_by == "popular":
        query = query.order_by((Post.like_count + Post.view_count).desc(), Post.created_at.desc())
    else:
        query = query.order_by(Post.created_at.desc())

    # 커서가 없으면 기존 offset 페이지네이션 사용
    if not cursor:
        query = query.offset((page - 1) * limit)
    query = query.limit(limit)

    result = await db.execute(query)
    posts = result.scalars().all()

    # 작성자 닉네임 + 플랜 배치 조회
    user_ids = [p.user_id for p in posts if p.user_id]
    nicknames: dict[str, str] = {}
    plans: dict[str, str] = {}
    if user_ids:
        ur = await db.execute(select(User.id, User.nickname, User.plan).where(User.id.in_(user_ids)))
        for row in ur.fetchall():
            nicknames[str(row[0])] = row[1] or "익명"
            plans[str(row[0])] = row[2]

    # 연관 이슈 제목 배치 조회 (한/영 분리)
    cluster_ids = [p.cluster_id for p in posts if p.cluster_id]
    cluster_titles_en: dict[str, str] = {}
    cluster_titles_ko: dict[str, str] = {}
    if cluster_ids:
        cr = await db.execute(
            select(IssueCluster.id, IssueCluster.title_ko, IssueCluster.title)
            .where(IssueCluster.id.in_(cluster_ids))
        )
        for row in cr.fetchall():
            cluster_titles_en[str(row[0])] = row[2] or row[1] or ""  # English first
            cluster_titles_ko[str(row[0])] = row[1] or row[2] or ""  # Korean first

    # 북마크 상태 배치 조회 (로그인 시)
    bookmarked_ids: set[str] = set()
    if current_user and posts:
        post_ids = [p.id for p in posts]
        br = await db.execute(
            select(Bookmark.post_id).where(
                Bookmark.user_id == current_user.id,
                Bookmark.post_id.in_(post_ids),
            )
        )
        bookmarked_ids = {str(row[0]) for row in br.fetchall()}

    post_list = [
        _post_to_out(
            p,
            nicknames.get(str(p.user_id)),
            cluster_titles_en.get(str(p.cluster_id)) if p.cluster_id else None,
            plans.get(str(p.user_id)),
            cluster_titles_ko.get(str(p.cluster_id)) if p.cluster_id else None,
            is_bookmarked=str(p.id) in bookmarked_ids,
        )
        for p in posts
    ]

    next_cursor = str(posts[-1].id) if len(posts) == limit else None
    return {"posts": post_list, "next_cursor": next_cursor}


@router.get("/hot-topics", response_model=list[PostOut])
async def hot_topics(
    post_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """오늘 자정 이후 생성된 글 중 핫토픽 상위 5개
    score = view_count + like_count * 3 - dislike_count * 1
    """
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)

    q = select(Post).where(Post.status == "active", Post.created_at >= today_start, Post.post_type != "notice")
    if post_type:
        q = q.where(Post.post_type == post_type)

    score_expr = Post.view_count + Post.like_count * 3 - Post.dislike_count * 1
    q = q.order_by(score_expr.desc()).limit(5)

    result = await db.execute(q)
    posts = result.scalars().all()

    user_ids = [p.user_id for p in posts if p.user_id]
    nicknames: dict[str, str] = {}
    plans: dict[str, str] = {}
    if user_ids:
        ur = await db.execute(select(User.id, User.nickname, User.plan).where(User.id.in_(user_ids)))
        for row in ur.fetchall():
            nicknames[str(row[0])] = row[1] or "익명"
            plans[str(row[0])] = row[2]

    return [
        _post_to_out(p, nicknames.get(str(p.user_id)), None, plans.get(str(p.user_id)))
        for p in posts
    ]


@router.get("/my-posts", response_model=list[PostOut])
async def my_posts(
    sort_by: str = Query("latest"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Post).where(Post.user_id == current_user.id, Post.status != "deleted")

    if sort_by == "popular":
        q = q.order_by((Post.like_count + Post.view_count).desc(), Post.created_at.desc())
    else:
        q = q.order_by(Post.created_at.desc())

    q = q.offset((page - 1) * limit).limit(limit)
    result = await db.execute(q)
    posts = result.scalars().all()

    return [
        _post_to_out(p, current_user.nickname, None, current_user.plan)
        for p in posts
    ]


@router.post("/posts", response_model=PostOut, status_code=201)
async def create_post(
    body: PostCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_active():
        raise HTTPException(403, detail="계정이 정지되었습니다.")

    if body.post_type not in ("discussion", "question", "analysis", "notice"):
        raise HTTPException(422, detail="유효하지 않은 게시글 유형입니다.")

    if body.post_type == "notice" and not current_user.is_admin():
        raise HTTPException(403, detail="공지사항은 관리자만 작성할 수 있습니다.")

    cluster_uuid = None
    if body.cluster_id:
        try:
            cluster_uuid = uuid.UUID(body.cluster_id)
        except ValueError:
            raise HTTPException(422, detail="유효하지 않은 cluster_id입니다.")

    images_val = body.images[:5] if body.images else None

    post = Post(
        user_id=current_user.id,
        cluster_id=cluster_uuid,
        title=body.title[:200],
        content=body.content,
        post_type=body.post_type,
        is_pinned=body.post_type == "notice",
        images=images_val,
    )
    post.title_en = await _translate_to_en(body.title[:200])
    post.content_en = await _translate_to_en(body.content[:5000])
    db.add(post)
    await db.flush()

    cluster_title = None
    cluster_title_ko = None
    if cluster_uuid:
        cr = await db.execute(
            select(IssueCluster.title_ko, IssueCluster.title)
            .where(IssueCluster.id == cluster_uuid)
        )
        crow = cr.one_or_none()
        if crow:
            cluster_title = crow[1] or crow[0]      # English first
            cluster_title_ko = crow[0] or crow[1]   # Korean first

    return _post_to_out(post, current_user.nickname, cluster_title, current_user.plan, cluster_title_ko)


@router.get("/posts/{post_id}", response_model=PostOut)
@limiter.limit("60/minute")
async def get_post(
    request: Request,
    post_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    try:
        pid = uuid.UUID(post_id)
    except ValueError:
        raise HTTPException(422, detail="유효하지 않은 post_id입니다.")

    result = await db.execute(select(Post).where(Post.id == pid, Post.status != "deleted"))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, detail="게시글을 찾을 수 없습니다.")

    # 조회수 +1
    post.view_count += 1
    await db.flush()

    nickname = None
    plan = None
    if post.user_id:
        ur = await db.execute(select(User.nickname, User.plan).where(User.id == post.user_id))
        row = ur.one_or_none()
        if row:
            nickname = row[0] or "익명"
            plan = row[1]

    cluster_title = None
    cluster_title_ko = None
    if post.cluster_id:
        cr = await db.execute(
            select(IssueCluster.title_ko, IssueCluster.title)
            .where(IssueCluster.id == post.cluster_id)
        )
        crow = cr.one_or_none()
        if crow:
            cluster_title = crow[1] or crow[0]      # English first
            cluster_title_ko = crow[0] or crow[1]   # Korean first

    # 북마크 상태 확인
    is_bookmarked = False
    if current_user:
        bm = await db.execute(
            select(Bookmark.id).where(
                Bookmark.user_id == current_user.id,
                Bookmark.post_id == pid,
            )
        )
        is_bookmarked = bm.scalar_one_or_none() is not None

    return _post_to_out(post, nickname, cluster_title, plan, cluster_title_ko, is_bookmarked=is_bookmarked)


@router.patch("/posts/{post_id}", response_model=PostOut)
async def update_post(
    post_id: str,
    body: PostCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        pid = uuid.UUID(post_id)
    except ValueError:
        raise HTTPException(422, detail="유효하지 않은 post_id입니다.")

    result = await db.execute(select(Post).where(Post.id == pid))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, detail="게시글을 찾을 수 없습니다.")
    if str(post.user_id) != str(current_user.id) and not current_user.is_admin():
        raise HTTPException(403, detail="수정 권한이 없습니다.")

    post.title = body.title[:200]
    post.content = body.content
    post.title_en = await _translate_to_en(body.title[:200])
    post.content_en = await _translate_to_en(body.content[:5000])
    if body.images is not None:
        post.images = body.images[:5] if body.images else None
    post.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return _post_to_out(post, current_user.nickname, None, current_user.plan)


@router.delete("/posts/{post_id}", status_code=204)
async def delete_post(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        pid = uuid.UUID(post_id)
    except ValueError:
        raise HTTPException(422, detail="유효하지 않은 post_id입니다.")

    result = await db.execute(select(Post).where(Post.id == pid))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, detail="게시글을 찾을 수 없습니다.")
    if str(post.user_id) != str(current_user.id) and not current_user.is_moderator():
        raise HTTPException(403, detail="삭제 권한이 없습니다.")

    post.status = "deleted"
    await db.flush()


@router.patch("/posts/{post_id}/pin", status_code=200)
async def toggle_pin(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """공지 상단고정 토글 (어드민 전용)"""
    if not current_user.is_admin():
        raise HTTPException(403, detail="관리자만 고정/해제할 수 있습니다.")

    try:
        pid = uuid.UUID(post_id)
    except ValueError:
        raise HTTPException(422, detail="유효하지 않은 post_id입니다.")

    result = await db.execute(select(Post).where(Post.id == pid))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, detail="게시글을 찾을 수 없습니다.")

    post.is_pinned = not post.is_pinned
    await db.flush()
    return {"is_pinned": post.is_pinned}


@router.post("/posts/{post_id}/react", status_code=200)
async def react_post(
    post_id: str,
    body: ReactionBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        pid = uuid.UUID(post_id)
    except ValueError:
        raise HTTPException(422)

    result = await db.execute(select(Post).where(Post.id == pid))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404)

    existing = await db.execute(
        select(PostReaction).where(PostReaction.user_id == current_user.id, PostReaction.post_id == pid)
    )
    reaction = existing.scalar_one_or_none()

    if reaction:
        if reaction.reaction_type == body.reaction_type:
            # 토글: 삭제
            db.delete(reaction)
            if body.reaction_type == "like":
                post.like_count = max(0, post.like_count - 1)
            elif body.reaction_type == "dislike":
                post.dislike_count = max(0, post.dislike_count - 1)
            return {"action": "removed"}
        else:
            # 반응 변경: 기존 카운트 감소 후 새 카운트 증가
            if reaction.reaction_type == "like":
                post.like_count = max(0, post.like_count - 1)
            elif reaction.reaction_type == "dislike":
                post.dislike_count = max(0, post.dislike_count - 1)
            reaction.reaction_type = body.reaction_type
            if body.reaction_type == "like":
                post.like_count += 1
            elif body.reaction_type == "dislike":
                post.dislike_count += 1
    else:
        db.add(PostReaction(user_id=current_user.id, post_id=pid, reaction_type=body.reaction_type))
        if body.reaction_type == "like":
            post.like_count += 1
        elif body.reaction_type == "dislike":
            post.dislike_count += 1

    await db.flush()
    return {"action": "added", "reaction_type": body.reaction_type}


# ── 북마크 ────────────────────────────────────────────────────────────────────

@router.post("/posts/{post_id}/bookmark", status_code=200)
async def toggle_bookmark(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """북마크 토글 (추가/제거)"""
    try:
        pid = uuid.UUID(post_id)
    except ValueError:
        raise HTTPException(422, detail="유효하지 않은 post_id입니다.")

    # 게시글 존재 확인
    result = await db.execute(select(Post).where(Post.id == pid, Post.status != "deleted"))
    if not result.scalar_one_or_none():
        raise HTTPException(404, detail="게시글을 찾을 수 없습니다.")

    # 기존 북마크 확인
    existing = await db.execute(
        select(Bookmark).where(Bookmark.user_id == current_user.id, Bookmark.post_id == pid)
    )
    bookmark = existing.scalar_one_or_none()

    if bookmark:
        await db.delete(bookmark)
        await db.flush()
        return {"bookmarked": False}
    else:
        db.add(Bookmark(user_id=current_user.id, post_id=pid))
        await db.flush()
        return {"bookmarked": True}


@router.get("/bookmarks", response_model=list[PostOut])
async def list_bookmarks(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내 북마크 목록"""
    # 북마크된 post_id를 created_at desc로 조회
    bm_q = (
        select(Bookmark.post_id)
        .where(Bookmark.user_id == current_user.id)
        .order_by(Bookmark.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    bm_result = await db.execute(bm_q)
    post_ids = [row[0] for row in bm_result.fetchall()]

    if not post_ids:
        return []

    # 게시글 조회
    result = await db.execute(
        select(Post).where(Post.id.in_(post_ids), Post.status != "deleted")
    )
    posts_map = {p.id: p for p in result.scalars().all()}

    # 북마크 순서 유지
    posts = [posts_map[pid] for pid in post_ids if pid in posts_map]

    # 작성자 닉네임 + 플랜 배치 조회
    user_ids = [p.user_id for p in posts if p.user_id]
    nicknames: dict[str, str] = {}
    plans: dict[str, str] = {}
    if user_ids:
        ur = await db.execute(select(User.id, User.nickname, User.plan).where(User.id.in_(user_ids)))
        for row in ur.fetchall():
            nicknames[str(row[0])] = row[1] or "익명"
            plans[str(row[0])] = row[2]

    # 연관 이슈 제목 배치 조회
    cluster_ids = [p.cluster_id for p in posts if p.cluster_id]
    cluster_titles_en: dict[str, str] = {}
    cluster_titles_ko: dict[str, str] = {}
    if cluster_ids:
        cr = await db.execute(
            select(IssueCluster.id, IssueCluster.title_ko, IssueCluster.title)
            .where(IssueCluster.id.in_(cluster_ids))
        )
        for row in cr.fetchall():
            cluster_titles_en[str(row[0])] = row[2] or row[1] or ""
            cluster_titles_ko[str(row[0])] = row[1] or row[2] or ""

    return [
        _post_to_out(
            p,
            nicknames.get(str(p.user_id)),
            cluster_titles_en.get(str(p.cluster_id)) if p.cluster_id else None,
            plans.get(str(p.user_id)),
            cluster_titles_ko.get(str(p.cluster_id)) if p.cluster_id else None,
            is_bookmarked=True,  # 북마크 목록이므로 항상 True
        )
        for p in posts
    ]


# ── 댓글 ─────────────────────────────────────────────────────────────────────

@router.post("/posts/{post_id}/comments", response_model=CommentOut, status_code=201)
async def create_comment(
    post_id: str,
    body: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_active():
        raise HTTPException(403, detail="계정이 정지되었습니다.")

    try:
        pid = uuid.UUID(post_id)
    except ValueError:
        raise HTTPException(422)

    result = await db.execute(select(Post).where(Post.id == pid, Post.status == "active"))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, detail="게시글을 찾을 수 없습니다.")

    parent_uuid = None
    if body.parent_id:
        try:
            parent_uuid = uuid.UUID(body.parent_id)
        except ValueError:
            raise HTTPException(422)

    comment = Comment(
        post_id=pid,
        user_id=current_user.id,
        parent_id=parent_uuid,
        content=body.content,
    )
    comment.content_en = await _translate_to_en(body.content[:5000])
    db.add(comment)
    post.comment_count += 1
    await db.flush()
    return _comment_to_out(comment, current_user.nickname)


@router.get("/posts/{post_id}/comments", response_model=list[CommentOut])
async def list_comments(
    post_id: str,
    limit: int = Query(100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    try:
        pid = uuid.UUID(post_id)
    except ValueError:
        raise HTTPException(422)

    result = await db.execute(
        select(Comment)
        .where(Comment.post_id == pid)
        .order_by(Comment.created_at.asc())
        .limit(limit)
    )
    comments = result.scalars().all()

    user_ids = [c.user_id for c in comments if c.user_id]
    nicknames: dict[str, str] = {}
    if user_ids:
        ur = await db.execute(select(User.id, User.nickname).where(User.id.in_(user_ids)))
        for row in ur.fetchall():
            nicknames[str(row[0])] = row[1] or "익명"

    return [_comment_to_out(c, nicknames.get(str(c.user_id))) for c in comments]


@router.patch("/comments/{comment_id}", response_model=CommentOut)
async def update_comment(
    comment_id: str,
    body: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        cid = uuid.UUID(comment_id)
    except ValueError:
        raise HTTPException(422)

    result = await db.execute(select(Comment).where(Comment.id == cid))
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(404)
    if str(comment.user_id) != str(current_user.id):
        raise HTTPException(403)

    comment.content = body.content
    comment.content_en = await _translate_to_en(body.content[:5000])
    comment.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return _comment_to_out(comment, current_user.nickname)


@router.delete("/comments/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        cid = uuid.UUID(comment_id)
    except ValueError:
        raise HTTPException(422)

    result = await db.execute(select(Comment).where(Comment.id == cid))
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(404)
    if str(comment.user_id) != str(current_user.id) and not current_user.is_moderator():
        raise HTTPException(403)

    comment.status = "deleted"
    await db.flush()


@router.post("/comments/{comment_id}/react", status_code=200)
async def react_comment(
    comment_id: str,
    body: ReactionBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        cid = uuid.UUID(comment_id)
    except ValueError:
        raise HTTPException(422)

    result = await db.execute(select(Comment).where(Comment.id == cid))
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(404)

    existing = await db.execute(
        select(CommentReaction).where(CommentReaction.user_id == current_user.id, CommentReaction.comment_id == cid)
    )
    reaction = existing.scalar_one_or_none()

    if reaction:
        if reaction.reaction_type == body.reaction_type:
            db.delete(reaction)
            if body.reaction_type == "like":
                comment.like_count = max(0, comment.like_count - 1)
            return {"action": "removed"}
        else:
            reaction.reaction_type = body.reaction_type
    else:
        db.add(CommentReaction(user_id=current_user.id, comment_id=cid, reaction_type=body.reaction_type))
        if body.reaction_type == "like":
            comment.like_count += 1

    await db.flush()
    return {"action": "added", "reaction_type": body.reaction_type}


# ── 신고 ─────────────────────────────────────────────────────────────────────

@router.post("/reports", status_code=201)
async def create_report(
    body: ReportCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.target_type not in ("post", "comment", "user"):
        raise HTTPException(422, detail="유효하지 않은 신고 유형입니다.")

    report = Report(
        reporter_id=current_user.id,
        target_type=body.target_type,
        target_id=body.target_id[:64],
        reason=body.reason[:200],
    )
    db.add(report)
    await db.flush()
    return {"status": "ok", "report_id": report.id}
