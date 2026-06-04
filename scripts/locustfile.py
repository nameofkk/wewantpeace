"""
WeWantPeace API 부하 테스트.

실행:
  locust -f scripts/locustfile.py --headless \
    -u 100 -r 10 --run-time 60s \
    --host http://localhost:8000
"""
from locust import HttpUser, task, between
import random


COUNTRIES = ["UA", "PS", "IL", "TW", "KR", "SY", "IR", "KP"]
DEV_UIDS = [f"loadtest-user-{i:03d}" for i in range(50)]


class AnonymousUser(HttpUser):
    """인증 없는 공개 엔드포인트 (트렌딩, 이슈, 건강체크)."""
    wait_time = between(1, 3)
    weight = 60  # 60% 비율

    @task(4)
    def get_global_trending(self):
        self.client.get("/trending/global", name="/trending/global")

    @task(3)
    def get_issues(self):
        code = random.choice(COUNTRIES)
        self.client.get(f"/issues?country_code={code}", name="/issues")

    @task(2)
    def get_tension_country(self):
        code = random.choice(COUNTRIES)
        self.client.get(f"/tension/country/{code}", name="/tension/country/{code}")

    @task(1)
    def health_check(self):
        self.client.get("/health", name="/health")


class AuthenticatedUser(HttpUser):
    """인증된 사용자 (관심지역, 긴장도, 트렌딩)."""
    wait_time = between(1, 4)
    weight = 40  # 40% 비율

    def on_start(self):
        self.uid = random.choice(DEV_UIDS)
        self.headers = {"X-Dev-UID": self.uid}

    @task(3)
    def get_me(self):
        self.client.get("/me", headers=self.headers, name="/me")

    @task(3)
    def get_tension_mine(self):
        self.client.get("/tension/mine", headers=self.headers, name="/tension/mine")

    @task(2)
    def get_my_areas(self):
        self.client.get("/me/areas", headers=self.headers, name="/me/areas")

    @task(2)
    def get_mine_trending(self):
        self.client.get("/trending/mine", headers=self.headers, name="/trending/mine")

    @task(1)
    def get_tension_history_7d(self):
        code = random.choice(COUNTRIES)
        self.client.get(
            f"/tension/country/{code}/history?range=7d",
            headers=self.headers,
            name="/tension/country/{code}/history?range=7d",
        )
