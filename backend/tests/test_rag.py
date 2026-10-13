from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

import main


def use_fake_llm(monkeypatch, reply="fake reply", error=None):
    prompts = []

    def fake(prompt_value):
        prompts.append(prompt_value.to_string())
        if error:
            raise error
        return AIMessage(content=reply)

    monkeypatch.setattr(main, "ChatOllama", lambda **kwargs: RunnableLambda(fake))
    return prompts


def pinecone_match(text, document_id, score=0.9):
    # Pinecone returns numeric metadata as floats, so mimic that
    return {"score": score, "metadata": {"text": text, "document_id": float(document_id)}}


# ---- classify_intent -------------------------------------------------------

@pytest.mark.parametrize("llm_reply, expected", [
    ("CHAT", "CHAT"),
    ("chat.", "CHAT"),
    ("DOCS", "DOCS"),
    ("banana", "DOCS"),
])
def test_classify_intent(monkeypatch, llm_reply, expected):
    use_fake_llm(monkeypatch, reply=llm_reply)

    assert main.classify_intent("anything") == expected


def test_classify_intent_model_down_returns_503(monkeypatch):
    use_fake_llm(monkeypatch, error=httpx.ConnectError("refused"))

    with pytest.raises(HTTPException) as exc:
        main.classify_intent("hi")

    assert exc.value.status_code == 503


# ---- generate_chat_reply ---------------------------------------------------

def test_chat_reply_includes_history_and_is_not_cacheable(monkeypatch):
    prompts = use_fake_llm(monkeypatch)
    history = [
        SimpleNamespace(role="user", content="my name is Sam"),
        SimpleNamespace(role="assistant", content="Nice to meet you, Sam"),
    ]

    result = main.generate_chat_reply("what is my name?", history)

    assert result == {"content": "fake reply", "citations": [], "cacheable": False}
    assert "my name is Sam" in prompts[0]


# ---- generate_answer -------------------------------------------------------

def test_chat_intent_skips_document_search(monkeypatch, db_session, fake_embed):
    monkeypatch.setattr(main, "classify_intent", lambda q: "CHAT")
    use_fake_llm(monkeypatch)

    result = main.generate_answer("hello", 1, [1], db_session, [])

    fake_embed.index.query.assert_not_called()
    assert result["citations"] == []
    assert result["cacheable"] is False


def test_no_matches_returns_fallback_without_calling_llm(monkeypatch, db_session, fake_embed):
    monkeypatch.setattr(main, "classify_intent", lambda q: "DOCS")
    prompts = use_fake_llm(monkeypatch)
    fake_embed.index.query.return_value = {"matches": []}

    result = main.generate_answer("question", 1, [1], db_session, [])

    assert result["content"] == main.NO_MATCH_ANSWER
    assert result["citations"] == []
    assert result["cacheable"] is False
    assert prompts == []


def test_matches_produce_answer_with_citations(monkeypatch, db_session, fake_embed, auth_headers, make_document):
    doc = make_document(auth_headers, "notes.pdf")
    monkeypatch.setattr(main, "classify_intent", lambda q: "DOCS")
    prompts = use_fake_llm(monkeypatch, reply="Paris.")
    fake_embed.index.query.return_value = {
        "matches": [pinecone_match("Paris is the capital of France.", doc.id)]
    }

    result = main.generate_answer("capital?", doc.user_id, [doc.id], db_session, [])

    assert result["content"] == "Paris."
    assert result["citations"] == [{"document": "notes.pdf"}]
    assert result["cacheable"] is True
    assert "Paris is the capital of France." in prompts[0]


def test_citations_never_include_other_users_documents(monkeypatch, db_session, fake_embed, auth_headers, other_headers, make_document):
    foreign_doc = make_document(other_headers, "secret.pdf")
    my_doc = make_document(auth_headers, "mine.pdf")
    monkeypatch.setattr(main, "classify_intent", lambda q: "DOCS")
    use_fake_llm(monkeypatch)
    fake_embed.index.query.return_value = {"matches": [pinecone_match("text", foreign_doc.id)]}

    result = main.generate_answer("q", my_doc.user_id, [my_doc.id], db_session, [])

    assert result["citations"] == []


def test_model_down_during_answer_returns_503(monkeypatch, db_session, fake_embed):
    monkeypatch.setattr(main, "classify_intent", lambda q: "DOCS")
    use_fake_llm(monkeypatch, error=httpx.ConnectError("refused"))
    fake_embed.index.query.return_value = {"matches": [pinecone_match("text", 1)]}

    with pytest.raises(HTTPException) as exc:
        main.generate_answer("q", 1, [1], db_session, [])

    assert exc.value.status_code == 503