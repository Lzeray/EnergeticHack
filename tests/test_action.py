from app.digest.action import derive_action_line
from app.pipeline.types import PipelineArticle


def art(title, text, tags=None):
    return PipelineArticle(
        id=1, source_id=1, source_name="src", source_priority=1.0,
        url="https://news.example.com/1", title=title, text=text,
        published_at=None, language="ru", tags=tags or [],
    )


def test_cve_article_gets_patch_action_for_technical_audience():
    a = art("Критическая уязвимость CVE-2024-1234", "описание", tags=["CVE-2024-1234"])
    assert "патч" in derive_action_line(a, "technical").lower()


def test_cve_article_gets_status_request_action_for_management():
    a = art("Критическая уязвимость CVE-2024-1234", "описание", tags=["CVE-2024-1234"])
    assert "статус" in derive_action_line(a, "management").lower()


def test_ransomware_keyword_triggers_backup_action():
    a = art("Ransomware атакует больницы", "Группировка шифрует данные медучреждений.")
    assert "резервные копии" in derive_action_line(a, "technical")


def test_supply_chain_keyword_triggers_cicd_action():
    a = art("Malicious npm package found", "A compromised dependency was published to the npm registry.")
    assert "CI/CD" in derive_action_line(a, "technical")


def test_unrelated_article_gets_default_action():
    a = art("Квартальный отчёт компании", "Финансовые результаты за квартал.")
    assert derive_action_line(a, "technical")
    assert derive_action_line(a, "management")
    assert derive_action_line(a, "technical") != derive_action_line(a, "management")
