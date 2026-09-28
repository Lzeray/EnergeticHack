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
