#!/usr/bin/env bash
# WeWantPeace PostgreSQL 백업 스크립트
#
# crontab 등록 예시 (매일 새벽 2시):
#   0 2 * * * /home/ubuntu/wewantpeace/scripts/backup.sh >> /var/log/wwp-backup.log 2>&1
#
# 환경변수:
#   DATABASE_URL   postgresql+asyncpg://user:pass@host/dbname
#   BACKUP_DIR     백업 저장 경로 (기본: /var/backups/wewantpeace)
#   BACKUP_RETAIN  보관 일수 (기본: 7)
#   S3_BUCKET      S3 버킷 (설정 시 S3에도 업로드)

set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_DIR:-/var/backups/wewantpeace}"
BACKUP_RETAIN="${BACKUP_RETAIN:-7}"
BACKUP_FILE="$BACKUP_DIR/wwp_${TIMESTAMP}.sql.gz"

# DATABASE_URL 파싱
# 형식: postgresql+asyncpg://user:pass@host:port/dbname
DB_URL="${DATABASE_URL:-}"
if [ -z "$DB_URL" ]; then
  echo "[$(date)] ERROR: DATABASE_URL 환경변수가 설정되지 않았습니다."
  exit 1
fi

# asyncpg → plain postgresql로 변환
PLAIN_URL="${DB_URL/postgresql+asyncpg/postgresql}"

echo "[$(date)] 백업 시작: $BACKUP_FILE"

# 백업 디렉토리 생성
mkdir -p "$BACKUP_DIR"

# pg_dump 실행 및 gzip 압축
pg_dump "$PLAIN_URL" \
  --format=plain \
  --no-password \
  --no-owner \
  --no-acl \
  | gzip > "$BACKUP_FILE"

BACKUP_SIZE=$(du -sh "$BACKUP_FILE" | cut -f1)
echo "[$(date)] 백업 완료: $BACKUP_FILE ($BACKUP_SIZE)"

# S3 업로드 (설정된 경우)
if [ -n "${S3_BUCKET:-}" ]; then
  S3_PATH="s3://$S3_BUCKET/wewantpeace/backups/wwp_${TIMESTAMP}.sql.gz"
  echo "[$(date)] S3 업로드 중: $S3_PATH"
  aws s3 cp "$BACKUP_FILE" "$S3_PATH" --storage-class STANDARD_IA
  echo "[$(date)] S3 업로드 완료"
fi

# 오래된 백업 정리
echo "[$(date)] ${BACKUP_RETAIN}일 이상 된 백업 삭제 중..."
find "$BACKUP_DIR" -name "wwp_*.sql.gz" -mtime +"$BACKUP_RETAIN" -delete
REMAINING=$(find "$BACKUP_DIR" -name "wwp_*.sql.gz" | wc -l)
echo "[$(date)] 남은 백업 파일: ${REMAINING}개"

echo "[$(date)] 백업 스크립트 완료"
