#!/usr/bin/env python3
"""
calibration.py → impact-factors.generated.json 동기화 스크립트.

worker/processor/calibration.py에서 IMPACT_FACTORS, TOPIC_IMPACT_WEIGHTS,
DEFAULT_IMPACT_FACTOR를 읽어 frontend/lib/impact-factors.generated.json으로 출력.

사용법:
    python scripts/sync_impact_factors.py          # JSON 파일 생성
    python scripts/sync_impact_factors.py --check   # 차이 여부만 확인 (CI용)
    python scripts/sync_impact_factors.py --stdout   # stdout으로 출력

실행 경로: 프로젝트 루트 (~/Projects/wewantpeace/)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ── 경로 설정 ────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CALIBRATION_MODULE = PROJECT_ROOT / "worker" / "processor" / "calibration.py"
OUTPUT_JSON = PROJECT_ROOT / "frontend" / "lib" / "impact-factors.generated.json"

# worker 패키지를 import할 수 있도록 sys.path에 프로젝트 루트 추가
sys.path.insert(0, str(PROJECT_ROOT))


def load_calibration_data() -> dict:
    """calibration.py 모듈에서 필요한 상수를 import하여 dict로 반환."""
    try:
        from worker.processor.calibration import (
            DEFAULT_IMPACT_FACTOR,
            IMPACT_FACTORS,
            TOPIC_IMPACT_WEIGHTS,
        )
    except ImportError as e:
        # import 실패 시 AST 파싱 폴백
        print(f"[WARN] 모듈 import 실패 ({e}), AST 파싱으로 전환", file=sys.stderr)
        return _parse_calibration_ast()

    return {
        "impact": IMPACT_FACTORS,
        "topic_weights": TOPIC_IMPACT_WEIGHTS,
        "default_factor": DEFAULT_IMPACT_FACTOR,
    }


def _parse_calibration_ast() -> dict:
    """AST를 사용하여 calibration.py에서 상수를 추출하는 폴백 방식."""
    import ast

    source = CALIBRATION_MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(CALIBRATION_MODULE))

    result: dict = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            name = target.id
            if name == "IMPACT_FACTORS":
                result["impact"] = ast.literal_eval(node.value)
            elif name == "TOPIC_IMPACT_WEIGHTS":
                result["topic_weights"] = ast.literal_eval(node.value)
            elif name == "DEFAULT_IMPACT_FACTOR":
                result["default_factor"] = ast.literal_eval(node.value)

    missing = {"impact", "topic_weights", "default_factor"} - set(result.keys())
    if missing:
        print(f"[ERROR] AST 파싱에서 누락된 키: {missing}", file=sys.stderr)
        sys.exit(1)

    return result


def to_json(data: dict) -> str:
    """정렬된 JSON 문자열 생성 (재현 가능한 출력)."""
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="calibration.py → impact-factors.generated.json 동기화",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="변경 여부만 확인 (CI용). 차이가 있으면 exit 1",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="파일 대신 stdout으로 출력",
    )
    args = parser.parse_args()

    data = load_calibration_data()
    new_json = to_json(data)

    if args.stdout:
        sys.stdout.write(new_json)
        return

    if args.check:
        if OUTPUT_JSON.exists():
            existing = OUTPUT_JSON.read_text(encoding="utf-8")
            if existing == new_json:
                print("[OK] impact-factors.generated.json 은 최신 상태입니다.")
                return
            else:
                print(
                    "[FAIL] impact-factors.generated.json 이 calibration.py와 다릅니다.",
                    file=sys.stderr,
                )
                print(
                    "  → 'python scripts/sync_impact_factors.py' 를 실행하세요.",
                    file=sys.stderr,
                )
                sys.exit(1)
        else:
            print(
                f"[FAIL] {OUTPUT_JSON} 파일이 없습니다.",
                file=sys.stderr,
            )
            sys.exit(1)

    # 파일 생성
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(new_json, encoding="utf-8")

    # 통계 출력
    impact = data["impact"]
    topics = data["topic_weights"]
    home_countries = list(impact.keys())
    total_pairs = sum(len(v) for v in impact.values())

    print(f"[OK] {OUTPUT_JSON.relative_to(PROJECT_ROOT)}")
    print(f"  기준국: {len(home_countries)}개 ({', '.join(home_countries)})")
    print(f"  영향 쌍: {total_pairs}개")
    print(f"  토픽: {len(topics)}개 ({', '.join(topics.keys())})")
    print(f"  기본값: {data['default_factor']}")


if __name__ == "__main__":
    main()
