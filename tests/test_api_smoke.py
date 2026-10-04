import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.main.init_db", lambda: None)
    monkeypatch.setattr("app.main.start_scheduler", lambda: None)
    monkeypatch.setattr("app.main.stop_scheduler", lambda: None)

    from app.config import settings

    monkeypatch.setattr(settings, "digests_dir", tmp_path)
    monkeypatch.setattr(settings, "settings_locked", False)

    from app.db import Base, get_session
    from app.main import app

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    from app import models  # noqa: F401

    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)

    def override_get_session():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_home_redirects_to_digest(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/digest"


def test_empty_state_pages_render(client):
    for path in ["/digest", "/sources", "/profiles", "/compare", "/metrics", "/settings"]:
        response = client.get(path)
        assert response.status_code == 200, path


def test_create_profile_and_source_then_generate_digest(client):
    resp = client.post("/profiles", data={"name": "Test Profile", "audience": "technical", "interests_text": "Приоритет: CVE, ransomware"}, follow_redirects=False)
    assert resp.status_code == 303

    resp = client.post(
        "/sources",
        data={"name": "Fixtures", "type": "dataset", "url_or_path": "articles_sample.json", "category": "media", "priority": "1.0"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    resp = client.post("/sources/1/fetch", follow_redirects=False)
    assert resp.status_code == 303

    sources_page = client.get("/sources")
    assert "Fixtures" in sources_page.text

    resp = client.post("/digest/generate", data={"profile_id": "1", "period_type": "daily"}, follow_redirects=False)
    assert resp.status_code == 303

    digest_page = client.get("/digest", params={"profile_id": 1, "period_type": "daily"})
    assert digest_page.status_code == 200
    assert "Материалов рассмотрено" in digest_page.text


def test_feedback_api_roundtrip(client):
    client.post("/profiles", data={"name": "P", "audience": "custom", "interests_text": "тест"})
    client.post("/sources", data={"name": "S", "type": "dataset", "url_or_path": "articles_sample.json", "category": "", "priority": "1.0"})
    client.post("/sources/1/fetch")

    response = client.post("/api/feedback", json={"profile_id": 1, "article_id": 1, "action": "like"})
    assert response.status_code == 200
    assert response.json()["ok"] is True

    response = client.post("/api/feedback", json={"profile_id": 1, "article_id": 1, "action": "dislike"})
    assert response.json()["action"] == "dislike"


def test_deleting_source_keeps_digest_and_metrics_working(client):
    client.post("/profiles", data={"name": "P", "audience": "technical", "interests_text": "CVE, ransomware"})
    client.post("/sources", data={"name": "S", "type": "dataset", "url_or_path": "articles_sample.json", "category": "", "priority": "1.0"})
    client.post("/sources/1/fetch")
    client.post("/digest/generate", data={"profile_id": "1", "period_type": "daily"})
    client.post("/api/feedback", json={"profile_id": 1, "article_id": 1, "action": "like"})

    resp = client.post("/sources/1/delete", follow_redirects=False)
    assert resp.status_code == 303

    assert client.get("/metrics").status_code == 200
    assert client.get("/digest", params={"profile_id": 1, "period_type": "daily"}).status_code == 200


def test_settings_page_never_renders_api_keys(client):
    client.post("/settings", data={"llm_provider": "openai", "openai_api_key": "sk-secret-123"})
    assert "sk-secret-123" not in client.get("/settings").text

    from app.db import get_session
    from app.main import app
    from app.runtime_settings import get_llm_config

    client.post("/settings", data={"llm_provider": "openai", "openai_api_key": ""})
    session = next(app.dependency_overrides[get_session]())
    assert get_llm_config(session)["openai_api_key"] == "sk-secret-123"


def test_locked_settings_reject_changes(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "settings_locked", True)
    resp = client.post("/settings", data={"llm_provider": "openai", "openai_base_url": "http://192.168.0.1"})
    assert resp.status_code == 403
    assert client.get("/settings").status_code == 200
