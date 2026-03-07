"""Add 22 new RSS/Telegram/Gov sources + API source fields

Revision ID: 0035
Revises: 0034
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. API 소스 지원을 위한 새 컬럼 추가 ──
    op.add_column("source_channels", sa.Column("api_endpoint", sa.String(), nullable=True))
    op.add_column("source_channels", sa.Column("api_params", sa.JSON(), nullable=True, server_default="{}"))
    op.add_column("source_channels", sa.Column("last_fetch_cursor", sa.String(), nullable=True))

    # ── 2. RSS 중동 전문매체 (4개, Day 0 배치) ──
    op.execute("""
        INSERT INTO source_channels (display_name, tier, base_confidence, language, topics, geo_focus, source_type, feed_url, is_active)
        VALUES
        ('Al Jazeera English', 'A', 0.90, 'en', '{conflict,diplomacy,protest}', '{ME,AF,AS}', 'rss', 'https://www.aljazeera.com/xml/rss/all.xml', true),
        ('Middle East Eye', 'B', 0.75, 'en', '{conflict,diplomacy,protest}', '{ME}', 'rss', 'https://www.middleeasteye.net/rss', true),
        ('Al-Monitor', 'B', 0.75, 'en', '{conflict,diplomacy,sanctions}', '{ME}', 'rss', 'https://www.al-monitor.com/rss', true),
        ('The New Arab', 'B', 0.75, 'en', '{conflict,protest,diplomacy}', '{ME}', 'rss', 'https://www.newarab.com/rss', true)
        ON CONFLICT DO NOTHING
    """)

    # ── 3. RSS 지역매체 + 싱크탱크 (8개, Day 3 배치) ──
    op.execute("""
        INSERT INTO source_channels (display_name, tier, base_confidence, language, topics, geo_focus, source_type, feed_url, is_active)
        VALUES
        ('Al Arabiya English', 'B', 0.75, 'en', '{conflict,diplomacy}', '{ME,SA}', 'rss', 'https://english.alarabiya.net/tools/rss', true),
        ('Anadolu Agency', 'B', 0.75, 'en', '{conflict,diplomacy,protest}', '{ME,TR}', 'rss', 'https://www.aa.com.tr/en/rss/default?cat=world', true),
        ('Middle East Monitor (MEMO)', 'B', 0.75, 'en', '{conflict,diplomacy,protest}', '{ME}', 'rss', 'https://www.middleeastmonitor.com/feed/', true),
        ('SANA (Syrian Arab News Agency)', 'C', 0.60, 'en', '{conflict,diplomacy}', '{SY}', 'rss', 'https://sana.sy/en/?feed=rss2', true),
        ('Syria Direct', 'B', 0.75, 'en', '{conflict,protest}', '{SY}', 'rss', 'https://syriadirect.org/feed/', true),
        ('International Crisis Group', 'A', 0.90, 'en', '{conflict,diplomacy,sanctions}', '{ME,AF,AS,EU}', 'rss', 'https://www.crisisgroup.org/rss.xml', true),
        ('IISS', 'A', 0.90, 'en', '{conflict,diplomacy,cyber}', '{ME,AS,EU}', 'rss', 'https://www.iiss.org/rss/', true),
        ('Carnegie Endowment', 'A', 0.90, 'en', '{conflict,diplomacy,sanctions}', '{ME,AS,EU,US}', 'rss', 'https://carnegieendowment.org/rss/solr/?query=*:*&lang=en', true)
        ON CONFLICT DO NOTHING
    """)

    # ── 4. Telegram 채널 (7개, Day 6 배치) ──
    op.execute("""
        INSERT INTO source_channels (display_name, tier, base_confidence, language, topics, geo_focus, source_type, username, is_active)
        VALUES
        ('Syria News (Telegram)', 'C', 0.60, 'ar', '{conflict}', '{SY}', 'telegram', 'SyriaNewsAr', true),
        ('Middle East Observer (Telegram)', 'C', 0.60, 'en', '{conflict,diplomacy}', '{ME}', 'telegram', 'MEObserver', true),
        ('Yemen Updates (Telegram)', 'C', 0.60, 'en', '{conflict}', '{YE}', 'telegram', 'YemenUpdates', true),
        ('Libya Observer (Telegram)', 'C', 0.60, 'en', '{conflict}', '{LY}', 'telegram', 'LibyaObserver', true),
        ('Iraq News (Telegram)', 'C', 0.60, 'ar', '{conflict,terror}', '{IQ}', 'telegram', 'IraqNewsNet', true),
        ('Sudan War Monitor (Telegram)', 'C', 0.60, 'en', '{conflict}', '{SD}', 'telegram', 'SudanWarMonitor', true),
        ('Lebanon Updates (Telegram)', 'C', 0.60, 'en', '{conflict,protest}', '{LB}', 'telegram', 'LebanonUpdates', true)
        ON CONFLICT DO NOTHING
    """)

    # ── 5. 정부기관 RSS (3개, Day 9 배치) ──
    op.execute("""
        INSERT INTO source_channels (display_name, tier, base_confidence, language, topics, geo_focus, source_type, feed_url, is_active)
        VALUES
        ('US State Department', 'B', 0.75, 'en', '{diplomacy,sanctions}', '{US,ME,AS,EU,AF}', 'rss', 'https://www.state.gov/rss-feed/press-releases/feed/', true),
        ('UK FCDO', 'B', 0.75, 'en', '{diplomacy,sanctions}', '{UK,ME,AS,EU,AF}', 'rss', 'https://www.gov.uk/government/organisations/foreign-commonwealth-development-office.atom', true),
        ('UN Security Council', 'A', 0.90, 'en', '{sanctions,diplomacy,conflict}', '{ME,AF,AS,EU}', 'rss', 'https://press.un.org/en/rss.xml', true)
        ON CONFLICT DO NOTHING
    """)

    # ── 6. API 소스 (3개, Day 12 배치) ──
    op.execute("""
        INSERT INTO source_channels (display_name, tier, base_confidence, language, topics, geo_focus, source_type, feed_url, api_endpoint, api_params, is_active)
        VALUES
        ('GDELT Project', 'B', 0.75, 'en', '{conflict,protest,diplomacy}', '{}', 'api', NULL, 'https://api.gdeltproject.org/api/v2/doc/doc', '{"mode":"ArtList","maxrecords":"50","timespan":"15min","format":"json","sort":"DateDesc"}', true),
        ('ACLED', 'A', 0.90, 'en', '{conflict,protest,terror}', '{}', 'api', NULL, 'https://api.acleddata.com/acled/read', '{"limit":"200","event_date_where":">=","fields":"event_id_cnty|event_date|event_type|sub_event_type|actor1|country|admin1|latitude|longitude|fatalities|notes|source"}', true),
        ('ReliefWeb', 'B', 0.75, 'en', '{conflict,disaster,health}', '{}', 'api', NULL, 'https://api.reliefweb.int/v1/reports', '{"appname":"wewantpeace","limit":"50","preset":"latest","fields[include][]":["title","body","date.created","country.name","disaster_type.name","source.name","url"]}', true)
        ON CONFLICT DO NOTHING
    """)

    # ── 7. ACTIVE_CHANNELS 코멘트 업데이트 (calibration.py에서 수동 변경 필요) ──
    # ACTIVE_CHANNELS: 37 → 58+ (코드에서 별도 변경)


def downgrade() -> None:
    # API 소스 삭제
    op.execute("DELETE FROM source_channels WHERE source_type = 'api'")
    # 정부기관 RSS 삭제
    op.execute("DELETE FROM source_channels WHERE display_name IN ('US State Department', 'UK FCDO', 'UN Security Council')")
    # Telegram 채널 삭제
    op.execute("DELETE FROM source_channels WHERE display_name IN ('Syria News (Telegram)', 'Middle East Observer (Telegram)', 'Yemen Updates (Telegram)', 'Libya Observer (Telegram)', 'Iraq News (Telegram)', 'Sudan War Monitor (Telegram)', 'Lebanon Updates (Telegram)')")
    # RSS 싱크탱크/지역매체 삭제
    op.execute("DELETE FROM source_channels WHERE display_name IN ('Al Arabiya English', 'Anadolu Agency', 'Middle East Monitor (MEMO)', 'SANA (Syrian Arab News Agency)', 'Syria Direct', 'International Crisis Group', 'IISS', 'Carnegie Endowment')")
    # RSS 중동 전문매체 삭제
    op.execute("DELETE FROM source_channels WHERE display_name IN ('Al Jazeera English', 'Middle East Eye', 'Al-Monitor', 'The New Arab')")
    # 컬럼 삭제
    op.drop_column("source_channels", "last_fetch_cursor")
    op.drop_column("source_channels", "api_params")
    op.drop_column("source_channels", "api_endpoint")
