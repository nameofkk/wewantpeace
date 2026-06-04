#!/usr/bin/env python3
"""
Natural Earth shapefile에서 국경 인접국(NEIGHBOR_MAP) 자동 생성.

geopandas + shapely를 사용하여 Natural Earth Admin 0 경계에서
touches/intersects 관계를 추출하고 ISO 3166-1 alpha-2 코드 기반
인접국 맵을 생성합니다.

사용법:
    python scripts/generate_neighbor_map.py                    # JSON 파일 생성
    python scripts/generate_neighbor_map.py --stdout           # stdout으로 출력
    python scripts/generate_neighbor_map.py --resolution 50m   # 50m 해상도 사용
    python scripts/generate_neighbor_map.py --compare           # 기존 NEIGHBOR_MAP과 비교

출력: worker/processor/neighbor_map.generated.json

의존성:
    pip install geopandas shapely
    (Natural Earth 데이터는 geopandas가 자동 다운로드)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

OUTPUT_JSON = PROJECT_ROOT / "worker" / "processor" / "neighbor_map.generated.json"


def check_dependencies() -> None:
    """geopandas/shapely 설치 여부 확인."""
    missing = []
    try:
        import geopandas  # noqa: F401
    except ImportError:
        missing.append("geopandas")
    try:
        import shapely  # noqa: F401
    except ImportError:
        missing.append("shapely")

    if missing:
        print(
            f"[ERROR] 필수 패키지가 설치되어 있지 않습니다: {', '.join(missing)}",
            file=sys.stderr,
        )
        print(
            f"\n  설치 방법:\n"
            f"    pip install {' '.join(missing)}\n"
            f"  또는:\n"
            f"    .venv/bin/pip install {' '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)


def load_natural_earth(resolution: str = "110m"):
    """Natural Earth Admin 0 데이터 로드."""
    import geopandas as gpd

    # geopandas 내장 Natural Earth 데이터셋 사용
    # 0.12+ 에서는 geodatasets를 통해 자동 다운로드
    try:
        world = gpd.read_file(
            gpd.datasets.get_path("naturalearth_lowres")
            if resolution == "110m"
            else f"https://naciscdn.org/naturalearth/{resolution}/cultural/ne_{resolution}_admin_0_countries.zip"
        )
    except Exception:
        # geopandas 최신 버전에서 datasets 경로가 바뀌었을 수 있음
        url = f"https://naciscdn.org/naturalearth/{resolution}/cultural/ne_{resolution}_admin_0_countries.zip"
        print(f"[INFO] Natural Earth 데이터 다운로드 중: {resolution}...", file=sys.stderr)
        world = gpd.read_file(url)

    return world


# ISO alpha-2 코드가 없거나 특수한 경우의 매핑
# Natural Earth의 iso_a2 필드가 '-99'인 국가들 보정
ISO_A2_FIXES: dict[str, str] = {
    "France": "FR",
    "Norway": "NO",
    "Kosovo": "XK",
    "N. Cyprus": "CY",       # 북키프로스 → 키프로스로 통합
    "Somaliland": "SO",       # 소말릴란드 → 소말리아로 통합
    "W. Sahara": "EH",
    "Dem. Rep. Congo": "CD",
    "Central African Rep.": "CF",
    "Eq. Guinea": "GQ",
    "eSwatini": "SZ",
    "S. Sudan": "SS",
    "Bosnia and Herz.": "BA",
    "Dominican Rep.": "DO",
    "Solomon Is.": "SB",
    "Timor-Leste": "TL",
}

# 해양 영토 / 종속 영토 제외 목록 (본토만 사용)
EXCLUDE_TERRITORIES: set[str] = {
    "AQ",   # 남극
    "TF",   # 프랑스 남방 및 남극 영토
    "HM",   # 허드 맥도널드 제도
    "BV",   # 부벳 섬
    "GS",   # 사우스조지아 사우스샌드위치
    "UM",   # 미국 외곽 소도
    "SJ",   # 스발바르 얀마옌
    "IO",   # 영국령 인도양
    "CX",   # 크리스마스 섬
    "CC",   # 코코스 제도
    "NF",   # 노퍽 섬
    "PN",   # 핏케언 제도
    "FK",   # 포클랜드 제도
}


def extract_iso_a2(row) -> str | None:
    """GeoDataFrame 행에서 ISO alpha-2 코드를 추출."""
    code = row.get("iso_a2", row.get("ISO_A2", row.get("ISO_A2_EH", "")))
    if code and code not in ("-99", "-1", ""):
        return code

    # 이름 기반 폴백
    name = row.get("name", row.get("NAME", row.get("ADMIN", "")))
    if name in ISO_A2_FIXES:
        return ISO_A2_FIXES[name]

    # iso_a2_eh 필드 시도 (Natural Earth 5.x+)
    code_eh = row.get("iso_a2_eh", row.get("ISO_A2_EH", ""))
    if code_eh and code_eh not in ("-99", "-1", ""):
        return code_eh

    return None


def build_neighbor_map(resolution: str = "110m", buffer_deg: float = 0.01) -> dict[str, list[str]]:
    """
    Natural Earth 데이터에서 인접국 맵 생성.

    Args:
        resolution: Natural Earth 해상도 ('110m', '50m', '10m')
        buffer_deg: 미세 간극 보정용 버퍼 (도 단위, 기본 0.01도 ~1.1km)

    Returns:
        {country_code: [neighbor_codes...]} 형태의 dict
    """
    import geopandas as gpd
    from shapely.validation import make_valid

    world = load_natural_earth(resolution)

    # ISO alpha-2 코드 할당
    world["cc"] = world.apply(extract_iso_a2, axis=1)

    # 코드 없는 행 제거
    world = world[world["cc"].notna()].copy()

    # 해양 영토 제외
    world = world[~world["cc"].isin(EXCLUDE_TERRITORIES)].copy()

    # 같은 국가 코드를 가진 행은 geometry 병합 (예: 프랑스 본토 + 해외 영토)
    # dissolve로 병합
    world = world.dissolve(by="cc", as_index=False)

    # geometry 유효성 보정
    world["geometry"] = world["geometry"].apply(make_valid)

    # 미세 간극 보정을 위한 버퍼 적용
    # 지리 좌표계(EPSG:4326)에서 buffer()는 부정확하지만,
    # 인접성 판별 목적으로는 충분. 경고 억제.
    import warnings
    world_buffered = world.copy()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        world_buffered["geometry"] = world_buffered["geometry"].buffer(buffer_deg)

    neighbor_map: dict[str, set[str]] = {}

    countries = world["cc"].tolist()
    geometries = world["geometry"].tolist()
    buffered_geometries = world_buffered["geometry"].tolist()

    print(f"[INFO] {len(countries)}개 국가 처리 중...", file=sys.stderr)

    for i, (cc_a, geom_a_buf) in enumerate(zip(countries, buffered_geometries)):
        if cc_a not in neighbor_map:
            neighbor_map[cc_a] = set()
        for j, (cc_b, geom_b) in enumerate(zip(countries, geometries)):
            if i >= j:
                continue
            if cc_a == cc_b:
                continue
            # 버퍼된 A가 원본 B와 교차하는지 확인
            try:
                if geom_a_buf.intersects(geom_b):
                    # 점 접촉만 있는 경우 (4국 경계점 등) 도 포함
                    neighbor_map.setdefault(cc_a, set()).add(cc_b)
                    neighbor_map.setdefault(cc_b, set()).add(cc_a)
            except Exception:
                continue

    # set → sorted list 변환
    result: dict[str, list[str]] = {}
    for cc in sorted(neighbor_map.keys()):
        neighbors = sorted(neighbor_map[cc])
        if neighbors:
            result[cc] = neighbors

    return result


def compare_with_existing(generated: dict[str, list[str]]) -> None:
    """기존 tension_calculator.py의 NEIGHBOR_MAP과 비교."""
    sys.path.insert(0, str(PROJECT_ROOT))

    try:
        # tension_calculator.py에서 직접 파싱
        import ast

        tc_path = PROJECT_ROOT / "worker" / "processor" / "tension_calculator.py"
        source = tc_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        existing: dict[str, list[str]] = {}
        for node in ast.walk(tree):
            # ast.Assign: NEIGHBOR_MAP = { ... }
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "NEIGHBOR_MAP":
                        existing = ast.literal_eval(node.value)
                        break
            # ast.AnnAssign: NEIGHBOR_MAP: dict[...] = { ... }
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.target.id == "NEIGHBOR_MAP":
                    existing = ast.literal_eval(node.value)
                    break

        if not existing:
            print("[WARN] 기존 NEIGHBOR_MAP을 찾을 수 없습니다.", file=sys.stderr)
            return

    except Exception as e:
        print(f"[WARN] 기존 NEIGHBOR_MAP 파싱 실패: {e}", file=sys.stderr)
        return

    # 비교
    all_countries = sorted(set(list(existing.keys()) + list(generated.keys())))

    added_countries = set(generated.keys()) - set(existing.keys())
    removed_countries = set(existing.keys()) - set(generated.keys())

    print(f"\n{'='*60}")
    print(f"기존 NEIGHBOR_MAP vs 생성된 맵 비교")
    print(f"{'='*60}")
    print(f"기존: {len(existing)}개 국가, 생성: {len(generated)}개 국가")

    if added_countries:
        print(f"\n[+] 새로 추가된 국가 ({len(added_countries)}개): {', '.join(sorted(added_countries))}")
    if removed_countries:
        print(f"\n[-] 기존에만 있는 국가 ({len(removed_countries)}개): {', '.join(sorted(removed_countries))}")

    # 공통 국가에서 이웃 차이
    diff_count = 0
    for cc in sorted(set(existing.keys()) & set(generated.keys())):
        old_set = set(existing.get(cc, []))
        new_set = set(generated.get(cc, []))
        added = new_set - old_set
        removed = old_set - new_set
        if added or removed:
            diff_count += 1
            parts = []
            if added:
                parts.append(f"+{','.join(sorted(added))}")
            if removed:
                parts.append(f"-{','.join(sorted(removed))}")
            print(f"  {cc}: {' '.join(parts)}")

    if diff_count == 0 and not added_countries and not removed_countries:
        print("\n  차이 없음!")
    else:
        print(f"\n  총 {diff_count}개 국가에서 이웃 변경")


def to_json(data: dict) -> str:
    """정렬된 JSON 문자열 생성."""
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Natural Earth shapefile에서 NEIGHBOR_MAP 자동 생성",
    )
    parser.add_argument(
        "--resolution",
        choices=["110m", "50m", "10m"],
        default="110m",
        help="Natural Earth 해상도 (기본: 110m, 세밀: 50m/10m)",
    )
    parser.add_argument(
        "--buffer",
        type=float,
        default=0.01,
        help="경계 버퍼 크기 (도 단위, 기본: 0.01)",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="파일 대신 stdout으로 출력",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="기존 tension_calculator.py의 NEIGHBOR_MAP과 비교",
    )
    args = parser.parse_args()

    check_dependencies()

    print(f"[INFO] Natural Earth {args.resolution} 데이터로 인접국 맵 생성 중...", file=sys.stderr)

    neighbor_map = build_neighbor_map(
        resolution=args.resolution,
        buffer_deg=args.buffer,
    )

    if args.compare:
        compare_with_existing(neighbor_map)
        print()

    json_str = to_json(neighbor_map)

    if args.stdout:
        sys.stdout.write(json_str)
        return

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json_str, encoding="utf-8")

    total_pairs = sum(len(v) for v in neighbor_map.values()) // 2
    print(f"[OK] {OUTPUT_JSON.relative_to(PROJECT_ROOT)}")
    print(f"  국가: {len(neighbor_map)}개")
    print(f"  인접 쌍: {total_pairs}개")

    # 상위 10개 (이웃 수 기준)
    top = sorted(neighbor_map.items(), key=lambda x: len(x[1]), reverse=True)[:10]
    print(f"\n  이웃 수 상위 10개:")
    for cc, neighbors in top:
        print(f"    {cc}: {len(neighbors)}개 → {', '.join(neighbors[:8])}{'...' if len(neighbors) > 8 else ''}")


if __name__ == "__main__":
    main()
