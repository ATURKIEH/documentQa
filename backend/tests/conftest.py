from unittest.mock import MagicMock

import embed_utils
embed_utils.EmbedUtils = MagicMock() 

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from models import Document
import models 
import main
from database import Base


class FakeRedis:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ex=None):
        self.store[key] = value


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session, monkeypatch):
    def override_get_db():
        yield db_session

    main.app.dependency_overrides[main.get_db] = override_get_db
    monkeypatch.setattr(main, "r", FakeRedis())
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()


def make_user(client, email="user@test.com", password="password123"):
    client.post("/auth/signup", json={"email": email, "password": password})
    response = client.post("/auth/login", data={"username": email, "password": password})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def auth_headers(client):
    return make_user(client)


@pytest.fixture()
def other_headers(client):
    return make_user(client, email="other@test.com")

@pytest.fixture(autouse=True)
def fake_embed(monkeypatch):
    """Fresh fake Pinecone/embeddings object for every test, so call counts never leak."""
    fake = MagicMock()
    monkeypatch.setattr(main, "embed_utils", fake)
    return fake


@pytest.fixture()
def create_chat(client):
    def _create(headers, title="Test chat", document_ids=None):
        return client.post(
            "/chats",
            json={"title": title, "document_ids": document_ids or []},
            headers=headers,
        )
    return _create


@pytest.fixture()
def make_document(client, db_session):
    def _make(headers, filename="notes.pdf"):
        user_id = client.get("/auth/me", headers=headers).json()["id"]
        doc = Document(user_id=user_id, filename=filename, pinecone_namespace=f"user_{user_id}")
        db_session.add(doc)
        db_session.commit()
        db_session.refresh(doc)
        return doc
    return _make


@pytest.fixture()
def chat_with_doc(create_chat, auth_headers, make_document):
    doc = make_document(auth_headers)
    chat_id = create_chat(auth_headers, document_ids=[doc.id]).json()["id"]
    return {"chat_id": chat_id, "doc": doc}