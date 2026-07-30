"""수집 파이프라인의 재시도·보존 기준 (단일 출처).

세 곳이 같은 기준을 알아야 하는데 각자 따로 하드코딩돼 있었고, 그 값들이 서로
어긋나면서 "백로그 과다" 경보가 영원히 해제되지 않는 문제를 만들었다:

  - retry_unprocessed : 최근 6시간 내 미처리 건만 재시도 (그보다 오래된 건 포기)
  - cleanup_old_data  : processed = true 인 행만 7일 후 삭제
  - _check_backlog    : processed = false 인 행을 **전부** 세서 300건 초과면 경보

결과: 6시간 안에 처리되지 못한 행은 재시도도 삭제도 되지 않고 영구히 남아
경보 카운터에만 계속 누적됐다 (2026-07-30 기준 5,547건이 2026-06-07부터 적체,
같은 시점 실제 살아있는 백로그는 43건).

세 값을 여기서 한 번만 정의해 다시 어긋나지 않게 한다.
"""

# retry_unprocessed가 재시도를 시도하는 범위. 이보다 오래된 미처리 건은
# 설계상 포기하며, 아래 보존 기간이 지나면 삭제된다.
UNPROCESSED_RETRY_WINDOW_HOURS = 6

# raw_events 보존 기간. processed 여부와 무관하게 이 기간이 지나면 삭제한다.
RAW_EVENT_RETENTION_DAYS = 7

# 백로그 경보 임계치. 재시도 대상(= 최근 UNPROCESSED_RETRY_WINDOW_HOURS 이내)
# 미처리 건수에만 적용한다.
BACKLOG_ALERT_THRESHOLD = 300
