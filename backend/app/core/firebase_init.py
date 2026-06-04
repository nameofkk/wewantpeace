"""
Firebase Admin SDK 초기화.

FIREBASE_SERVICE_ACCOUNT_JSON 환경변수에서 서비스 계정 JSON을 읽어 초기화.
이 변수가 없으면 초기화 생략 (토큰 검증 불가).
"""
import os
import logging

logger = logging.getLogger(__name__)

_initialized = False


def init_firebase() -> bool:
    """
    Firebase Admin SDK 초기화. 앱 시작 시 1회 호출.

    Returns:
        True if initialized successfully, False otherwise.
    """
    global _initialized
    if _initialized:
        return True

    service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if not service_account_json:
        logger.warning(
            "FIREBASE_SERVICE_ACCOUNT_JSON 환경변수가 없습니다. "
            "Firebase 토큰 검증이 비활성화됩니다. "
            "Firebase Console > 프로젝트 설정 > 서비스 계정 > 새 비공개 키 생성"
        )
        return False

    try:
        import json
        import firebase_admin
        from firebase_admin import credentials

        if not firebase_admin._apps:
            service_account_info = json.loads(service_account_json)
            cred = credentials.Certificate(service_account_info)
            firebase_admin.initialize_app(cred)

        _initialized = True
        logger.info("Firebase Admin SDK 초기화 완료 ✓")
        return True

    except Exception as e:
        logger.error("Firebase Admin SDK 초기화 실패: %s", e)
        return False
