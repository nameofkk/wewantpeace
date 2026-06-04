"""term_versions and user_consents

Revision ID: 0007
Revises: 0006
Create Date: 2025-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None

TERMS_V1 = """제1조(목적)
이 약관은 WeWantPeace(이하 "회사")가 제공하는 서비스의 이용조건 및 절차, 회사와 이용자의 권리·의무 및 책임사항을 규정함을 목적으로 합니다.

제2조(정의)
① "서비스"란 회사가 제공하는 세계정세 알림·지도·커뮤니티 플랫폼을 말합니다.
② "회원"이란 본 약관에 동의하고 서비스를 이용하는 자를 말합니다.
③ "Pro 회원"이란 유료 구독을 통해 추가 기능을 이용하는 회원을 말합니다.
④ "콘텐츠"란 회원이 서비스 내에서 작성·게시한 게시물, 댓글 등을 말합니다.

제3조(서비스 제공 및 변경)
① 회사는 연중무휴 24시간 서비스를 제공합니다.
② 회사는 서비스 내용을 변경할 경우 최소 7일 전에 공지합니다.
③ 정기점검 등 기술상 이유로 서비스가 일시 중단될 수 있습니다.

제4조(이용계약 체결)
① 서비스 이용은 만 14세 이상만 가능합니다.
② 이용자는 회원가입 시 본 약관 및 개인정보처리방침에 동의해야 합니다.
③ 허위 정보 제공 시 이용이 제한될 수 있습니다.

제5조(회원 의무 및 금지행위)
회원은 다음 행위를 해서는 안 됩니다:
① 타인의 계정 도용 또는 허위 정보 등록
② 허위 뉴스, 선동적 콘텐츠 게시
③ 스팸, 광고성 게시물 반복 게시
④ 저작권 침해 콘텐츠 게시
⑤ 혐오 발언, 명예훼손 발언
⑥ 서비스 해킹 또는 비정상적 접근 시도
⑦ 다중 계정 생성 및 어뷰징

제6조(서비스 제공자 의무)
① 회사는 안정적인 서비스 제공을 위해 최선을 다합니다.
② 회사는 이용자의 개인정보를 개인정보처리방침에 따라 보호합니다.
③ 회원의 불만·피해 구제에 최선을 다합니다.

제7조(유료서비스 및 결제)
① Pro 구독: 월 4,900원 / Pro+ 구독: 월 9,900원 (VAT 포함)
② 결제는 토스페이먼츠를 통한 정기결제 방식으로 진행됩니다.
③ 구독 취소 시 현재 기간 만료까지 서비스 이용 가능합니다.
④ 서비스 이용 후 7일 이내에는 전액 환불이 가능합니다.
⑤ 환불 요청: krshin7@naver.com

제8조(책임제한)
① 천재지변, 불가항력에 의한 서비스 장애는 회사 책임에서 제외됩니다.
② Firebase, Toss Payments 등 제3자 서비스 장애는 회사 책임에서 제외됩니다.
③ 이용자 귀책으로 발생한 손해는 회사가 책임지지 않습니다.

제9조(분쟁해결)
서비스 이용 관련 분쟁은 한국소비자원 또는 전자거래분쟁조정위원회를 통해 해결할 수 있습니다.

제10조(준거법 및 관할)
본 약관은 대한민국 법률을 준거법으로 하며, 분쟁 시 서울중앙지방법원을 전속 관할로 합니다.

부칙
본 약관은 2025년 1월 1일부터 시행합니다."""

PRIVACY_V1 = """개인정보처리방침

WeWantPeace(이하 "회사")는 개인정보보호법, 정보통신망 이용촉진 및 정보보호 등에 관한 법률을 준수합니다.

1. 수집하는 개인정보 항목
[필수] 이메일 주소, 닉네임, 생년도, 소셜로그인 식별자(Google UID 등)
[선택] 프로필 사진, 자기소개(bio)
[자동] IP주소, 접속 로그, 쿠키, 서비스 이용 기록

2. 수집 목적 및 이용 목적
- 회원 가입 및 관리
- 서비스 제공 및 개인화
- 유료 서비스 결제 처리
- 불법 이용 방지 및 보안
- 서비스 개선을 위한 통계 분석

3. 보유 및 이용 기간
- 회원 탈퇴 시 즉시 파기 (닉네임 및 이메일 익명 처리)
- 단, 관련 법령에 따라 보관:
  * 계약/청약 철회 기록: 5년 (전자상거래법)
  * 소비자 불만 처리: 3년 (전자상거래법)
  * 부정 이용 방지: 1년

4. 개인정보 제3자 제공
- Firebase (Google Inc.): 인증 서비스 제공 목적
- Toss Payments (주식회사 토스페이먼츠): 결제 처리 목적
- 법령에 따른 수사기관 요청 시 제공 가능

5. 개인정보 처리 위탁
- 클라우드 인프라: Fly.io (서버 운영)
- 위탁 업무 외 개인정보 처리 금지 계약 체결

6. 이용자 권리 행사 방법
이용자는 언제든지 다음 권리를 행사할 수 있습니다:
- 개인정보 열람, 정정, 삭제 요청
- 개인정보 처리 정지 요청
- 요청 처리: 14일 이내
- 연락처: krshin7@naver.com

7. 자동 수집 장치 (쿠키)
- 세션 관리 및 서비스 이용 분석에 쿠키 사용
- 브라우저 설정으로 쿠키 거부 가능 (일부 서비스 제한 가능)

8. 개인정보 안전성 확보 조치
- 개인정보 전송 시 HTTPS(TLS) 암호화
- 접근 권한 최소화 (역할 기반 접근 제어)
- 비밀번호 해시화 저장
- 정기적 보안 점검

9. 개인정보 보호책임자
성명: WeWantPeace 개인정보 보호담당자
이메일: krshin7@naver.com
연락처: krshin7@naver.com

10. 고지의 의무
이 개인정보처리방침은 변경될 경우 서비스 내 공지사항 또는 이메일을 통해 사전 고지합니다.

시행일: 2025년 1월 1일"""


def upgrade() -> None:
    op.create_table(
        'term_versions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('type', sa.String(16), nullable=False),
        sa.Column('version', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('effective_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("type IN ('terms','privacy')", name='ck_term_versions_type'),
        sa.UniqueConstraint('type', 'version', name='uq_term_type_version'),
    )

    op.create_table(
        'user_consents',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('term_type', sa.String(16), nullable=False),
        sa.Column('term_version', sa.String(20), nullable=False),
        sa.Column('agreed_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
    )
    op.create_index('ix_user_consents_user_id', 'user_consents', ['user_id'])

    # 초기 약관 데이터
    op.execute(
        sa.text("""
        INSERT INTO term_versions (type, version, content, effective_at)
        VALUES
          ('terms', '1.0', :terms_content, '2025-01-01 00:00:00+00'),
          ('privacy', '1.0', :privacy_content, '2025-01-01 00:00:00+00')
        """).bindparams(terms_content=TERMS_V1, privacy_content=PRIVACY_V1)
    )


def downgrade() -> None:
    op.drop_table('user_consents')
    op.drop_table('term_versions')
