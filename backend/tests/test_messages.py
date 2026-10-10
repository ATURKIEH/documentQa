from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

import main
from models import ChatDocument

PAYLOAD = {
    "content": "Paris is the capital.",
    "citations": [{"document": "notes.pdf"}],
    "cacheable": True,
}


@pytest.fixture()
def fake_generate(monkeypatch):
    mock = MagicMock(return_value=dict(PAYLOAD))
    monkeypatch.setattr(main, "generate_answer", mock)
    return mock


def post_message(client, headers, chat_id, content="What is the capital?"):
    return client.post(f"/chats/{chat_id}/messages", json={"content": content}, headers=headers)


def get_messages(client, headers, chat_id):
    detail = client.get(f"/chats/{chat_id}", headers=headers).json()
    return sorted(detail["messages"], key=lambda m: m["id"])


def test_send_message_returns_assistant_reply_with_citations(client, auth_headers, chat_with_doc, fake_generate):
    response = post_message(client, auth_headers, chat_with_doc["chat_id"])

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "assistant"
    assert body["content"] == "Paris is the capital."
    assert body["citations"] == [{"document": "notes.pdf"}]


def test_both_messages_are_saved_in_order(client, auth_headers, chat_with_doc, fake_generate):
    chat_id = chat_with_doc["chat_id"]
    post_message(client, auth_headers, chat_id, "What is the capital?")

    messages = get_messages(client, auth_headers, chat_id)

    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "What is the capital?"
    assert messages[1]["citations"] == [{"document": "notes.pdf"}]


def test_generate_answer_receives_the_question(client, auth_headers, chat_with_doc, fake_generate):
    post_message(client, auth_headers, chat_with_doc["chat_id"], "Who wrote it?")

    fake_generate.assert_called_once()
    assert fake_generate.call_args.args[0] == "Who wrote it?"


def test_chat_without_documents_returns_400_and_saves_nothing(client, auth_headers, create_chat, fake_generate):
    chat_id = create_chat(auth_headers).json()["id"]

    response = post_message(client, auth_headers, chat_id)

    assert response.status_code == 400
    assert get_messages(client, auth_headers, chat_id) == []
    fake_generate.assert_not_called()


def test_send_message_requires_auth(client, chat_with_doc, fake_generate):
    assert post_message(client, {}, chat_with_doc["chat_id"]).status_code == 401


def test_send_message_to_other_users_chat_returns_404(client, other_headers, chat_with_doc, fake_generate):
    assert post_message(client, other_headers, chat_with_doc["chat_id"]).status_code == 404
    fake_generate.assert_not_called()


def test_send_message_to_missing_chat_returns_404(client, auth_headers, fake_generate):
    assert post_message(client, auth_headers, 99999).status_code == 404


def test_model_failure_returns_503_and_saves_nothing(client, auth_headers, chat_with_doc, fake_generate):
    fake_generate.side_effect = HTTPException(status_code=503, detail="down")
    chat_id = chat_with_doc["chat_id"]

    response = post_message(client, auth_headers, chat_id)

    assert response.status_code == 503
    assert get_messages(client, auth_headers, chat_id) == []


def test_same_question_is_served_from_cache(client, auth_headers, chat_with_doc, fake_generate):
    chat_id = chat_with_doc["chat_id"]

    first = post_message(client, auth_headers, chat_id)
    second = post_message(client, auth_headers, chat_id)

    assert fake_generate.call_count == 1
    assert second.json()["content"] == first.json()["content"]
    assert second.json()["citations"] == first.json()["citations"]
    assert len(get_messages(client, auth_headers, chat_id)) == 4  # both exchanges are saved


def test_different_question_is_not_cached(client, auth_headers, chat_with_doc, fake_generate):
    chat_id = chat_with_doc["chat_id"]

    post_message(client, auth_headers, chat_id, "first question")
    post_message(client, auth_headers, chat_id, "second question")

    assert fake_generate.call_count == 2


def test_non_cacheable_answers_are_not_cached(client, auth_headers, chat_with_doc, fake_generate):
    fake_generate.return_value = {**PAYLOAD, "cacheable": False}
    chat_id = chat_with_doc["chat_id"]

    post_message(client, auth_headers, chat_id)
    post_message(client, auth_headers, chat_id)

    assert fake_generate.call_count == 2


def test_cache_is_invalidated_when_documents_change(client, db_session, auth_headers, chat_with_doc, make_document, fake_generate):
    chat_id = chat_with_doc["chat_id"]
    post_message(client, auth_headers, chat_id)

    second_doc = make_document(auth_headers, "more.pdf")
    db_session.add(ChatDocument(chat_id=chat_id, document_id=second_doc.id))
    db_session.commit()
    post_message(client, auth_headers, chat_id)

    assert fake_generate.call_count == 2


def test_history_is_passed_to_generate_answer(client, auth_headers, chat_with_doc, fake_generate):
    chat_id = chat_with_doc["chat_id"]
    post_message(client, auth_headers, chat_id, "first question")
    post_message(client, auth_headers, chat_id, "second question")

    history = fake_generate.call_args_list[1].args[4]  # 5th positional arg; adjust if your signature differs
    assert len(history) == 2