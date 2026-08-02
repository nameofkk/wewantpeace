"""
FIRMS 유입량 실측 — MIN_FRP_VIIRS 재조정용 (읽기 전용, DB 미접속).

firms_collector.py의 임계는 2026-08-03 스냅샷으로 정했다. 그런데 FIRMS 유입량은
계절(북반구 산불 성수기 6~9월 vs 겨울)에 따라 몇 배씩 흔들린다. 임계를 다시 볼 때
이 스크립트로 재측정한다.

실행:
    FIRMS_MAP_KEY=... python scripts/measure_firms_volume.py

출력:
    - 센서별 CSV 행수 / confidence 분포 / 필터 통과 행수
    - VIIRS FRP 분위수
    - 임계 후보별: 정상상태 예상 행수, intensity 유지율, /signals/firms 페이로드 크기

읽는 법: intensity(= min(1, frp/500) * confidence)가 실제 산출물이다. 지도
heatmap-weight와 correlator의 confidence 보정이 모두 이 값을 쓴다. 그래서 임계를
고를 때는 행수가 아니라 'intensity 유지율 대비 행수 감소'를 본다.
"""
import os
import statistics
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

CSV_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{map_key}/{source}/world/2"
SENSORS = ["MODIS_NRT", "VIIRS_NOAA20_NRT"]

MIN_CONFIDENCE_MODIS = 50
VIIRS_CONFIDENCE_MULTIPLIER = {"n": 0.8, "nominal": 0.8, "h": 1.0, "high": 1.0}

# 정상상태 창: expires_at = observed_at + 24h 이고 cleanup_expired_signals가
# 6시간마다 도니 최대 30h치가 테이블에 남는다.
WINDOW_HOURS = 30
# /signals/firms GeoJSON 실측 (routers/signals.py의 _to_geojson 기준)
BYTES_PER_FEATURE = 393.5

NOW = datetime.now(timezone.utc)
CUTOFF = NOW - timedelta(hours=WINDOW_HOURS)


def fetch(map_key: str, source: str) -> str:
    url = CSV_URL.format(map_key=map_key, source=source)
    with urllib.request.urlopen(url, timeout=180) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse(source: str, text: str):
    """firms_collector.collect()의 행 처리 규칙과 동일 (confidence 필터까지)."""
    lines = text.strip().split("\n")
    col_map = {h.strip(): i for i, h in enumerate(lines[0].split(","))}
    rows, conf_dist = [], {}
    for line in lines[1:]:
        try:
            cols = line.split(",")
            lat = float(cols[col_map["latitude"]])
            lon = float(cols[col_map["longitude"]])
            conf_raw = cols[col_map["confidence"]].strip()
            conf_dist[conf_raw] = conf_dist.get(conf_raw, 0) + 1

            if source.startswith("MODIS"):
                conf_val = int(conf_raw)
                if conf_val < MIN_CONFIDENCE_MODIS:
                    continue
                mult = conf_val / 100.0
            else:
                mult = VIIRS_CONFIDENCE_MULTIPLIER.get(conf_raw.lower())
                if mult is None:
                    continue

            frp = float(cols[col_map["frp"]].strip())
            acq_date = cols[col_map["acq_date"]].strip()
            acq_time = cols[col_map["acq_time"]].strip() or "0000"
            try:
                observed_at = datetime.strptime(
                    f"{acq_date} {acq_time}", "%Y-%m-%d %H%M"
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                observed_at = NOW

            external_id = f"firms:{source}:{acq_date}:{round(lat, 3)}:{round(lon, 3)}"
            rows.append((external_id, frp, min(1.0, frp / 500.0) * mult, observed_at))
        except (IndexError, ValueError, KeyError):
            continue
    return rows, conf_dist


def window(rows, min_frp):
    """정상상태 창 안의 유니크 external_id 수와 intensity 총량."""
    seen, intensity_sum = set(), 0.0
    for external_id, frp, intensity, observed_at in rows:
        if frp < min_frp or observed_at < CUTOFF or external_id in seen:
            continue
        seen.add(external_id)
        intensity_sum += intensity
    return len(seen), intensity_sum


def main() -> int:
    map_key = os.environ.get("FIRMS_MAP_KEY", "")
    if not map_key:
        print("FIRMS_MAP_KEY 환경변수 필요", file=sys.stderr)
        return 1

    parsed = {}
    for source in SENSORS:
        rows, conf_dist = parse(source, fetch(map_key, source))
        parsed[source] = rows
        top = sorted(conf_dist.items(), key=lambda kv: -kv[1])[:6]
        print(f"[{source}] confidence 필터 통과 {len(rows):,}행  분포(상위) {top}")

    modis_rows, modis_intensity = window(parsed["MODIS_NRT"], 10)
    print(f"\nMODIS 대조군 ({WINDOW_HOURS}h 창, MIN_FRP=10): "
          f"{modis_rows:,}행  intensity합 {modis_intensity:,.1f}")

    viirs = parsed["VIIRS_NOAA20_NRT"]
    frps = sorted(r[1] for r in viirs if r[1] >= 10)
    if frps:
        q = statistics.quantiles(frps, n=100)
        print("\nVIIRS FRP 분위수 (frp>=10 통과분): "
              + "  ".join(f"p{p}={q[p - 1]:.1f}" for p in (50, 75, 90, 95, 99)))

    base_rows, base_intensity = window(viirs, 10)
    print(f"\n{'임계':>5} {'VIIRS행':>9} {'행유지':>7} {'int유지':>8} "
          f"{'합계행수':>9} {'vs MODIS':>9} {'GeoJSON':>9}")
    print("-" * 62)
    for thr in (10, 15, 20, 25, 30, 40, 50, 75, 100):
        n, isum = window(viirs, thr)
        total = modis_rows + n
        print(f"{thr:>5} {n:>9,} {n / base_rows * 100:>6.1f}% "
              f"{isum / base_intensity * 100:>7.1f}% {total:>9,} "
              f"{n / modis_rows:>8.2f}x {total * BYTES_PER_FEATURE / 1024 / 1024:>7.2f}MB")

    print("\n현재 설정: MIN_FRP_VIIRS=20 (worker/collector/firms_collector.py)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
