def test_create_chat(client, auth_headers, create_chat):
    response = create_chat(auth_headers, title="My chat")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "My chat"
    assert body["documents"] == []


def test_create_chat_without_title_uses_default(client, auth_headers):
    response = client.post("/chats", json={}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["title"] == "New Chat"


def test_create_chat_with_document_lists_its_name(auth_headers, create_chat, make_document):
    doc = make_document(auth_headers, "report.pdf")

    response = create_chat(auth_headers, document_ids=[doc.id])

    assert response.status_code == 200
    assert response.json()["documents"] == ["report.pdf"]


def test_create_chat_with_missing_document_returns_404(auth_headers, create_chat):
    assert create_chat(auth_headers, document_ids=[99999]).status_code == 404


def test_create_chat_with_other_users_document_returns_404(auth_headers, other_headers, create_chat, make_document):
    doc = make_document(auth_headers)

    assert create_chat(other_headers, document_ids=[doc.id]).status_code == 404


def test_list_chats_requires_auth(client):
    assert client.get("/chats").status_code == 401


def test_list_chats_only_returns_own(client, auth_headers, other_headers, create_chat):
    create_chat(auth_headers, "one")
    create_chat(auth_headers, "two")
    create_chat(other_headers, "theirs")

    mine = client.get("/chats", headers=auth_headers).json()
    theirs = client.get("/chats", headers=other_headers).json()

    assert sorted(c["title"] for c in mine) == ["one", "two"]
    assert [c["title"] for c in theirs] == ["theirs"]


def test_get_chat_detail(client, auth_headers, create_chat):
    chat_id = create_chat(auth_headers).json()["id"]

    response = client.get(f"/chats/{chat_id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["messages"] == []


def test_get_other_users_chat_returns_404(client, auth_headers, other_headers, create_chat):
    chat_id = create_chat(auth_headers).json()["id"]

    assert client.get(f"/chats/{chat_id}", headers=other_headers).status_code == 404


def test_get_missing_chat_returns_404(client, auth_headers):
    assert client.get("/chats/99999", headers=auth_headers).status_code == 404


def test_delete_chat(client, auth_headers, create_chat):
    chat_id = create_chat(auth_headers).json()["id"]

    assert client.delete(f"/chats/{chat_id}", headers=auth_headers).status_code == 200
    assert client.get(f"/chats/{chat_id}", headers=auth_headers).status_code == 404


def test_delete_other_users_chat_returns_404_and_keeps_it(client, auth_headers, other_headers, create_chat):
    chat_id = create_chat(auth_headers).json()["id"]

    assert client.delete(f"/chats/{chat_id}", headers=other_headers).status_code == 404
    assert client.get(f"/chats/{chat_id}", headers=auth_headers).status_code == 200