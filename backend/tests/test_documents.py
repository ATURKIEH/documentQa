from pathlib import Path

import fitz
import pytest
import pytesseract

from document_utils import DocumentUtils
from models import Document

TEXT = b"Cats are small domesticated mammals that people keep as pets."


@pytest.fixture(autouse=True)
def isolate_cwd(tmp_path, monkeypatch):
    """The upload endpoint writes to ./uploaded_files, so run every test in a temp folder."""
    monkeypatch.chdir(tmp_path)


def upload(client, headers, name="notes.txt", content=TEXT, path="/documents/upload"):
    return client.post(path, files={"file": (name, content, "text/plain")}, headers=headers)


# ---- upload endpoints ------------------------------------------------------

def test_upload_stores_document_and_chunks(client, db_session, auth_headers, fake_embed):
    response = upload(client, auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "notes.txt"
    assert body["chunks_stored"] >= 1
    assert db_session.query(Document).filter(Document.id == body["document_id"]).first() is not None
    fake_embed.store_document_chunks.assert_called_once()
    assert fake_embed.store_document_chunks.call_args.kwargs["document_id"] == body["document_id"]


def test_upload_requires_auth(client):
    assert upload(client, {}).status_code == 401


def test_upload_removes_temp_file(client, auth_headers):
    upload(client, auth_headers)

    leftovers = [p for p in Path("uploaded_files").rglob("*") if p.is_file()]
    assert leftovers == []


def test_upload_with_no_text_returns_422_and_keeps_no_row(client, db_session, auth_headers):
    response = upload(client, auth_headers, name="empty.txt", content=b"   ")

    assert response.status_code == 422
    assert db_session.query(Document).count() == 0


def test_upload_to_chat_attaches_document(client, auth_headers, create_chat):
    chat_id = create_chat(auth_headers).json()["id"]

    response = upload(client, auth_headers, path=f"/chats/{chat_id}/documents")

    assert response.status_code == 200
    assert response.json()["documents"] == ["notes.txt"]
    detail = client.get(f"/chats/{chat_id}", headers=auth_headers).json()
    assert detail["documents"] == ["notes.txt"]


def test_upload_to_other_users_chat_returns_404(client, db_session, auth_headers, other_headers, create_chat):
    chat_id = create_chat(auth_headers).json()["id"]

    response = upload(client, other_headers, path=f"/chats/{chat_id}/documents")

    assert response.status_code == 404
    assert db_session.query(Document).count() == 0


# ---- text extraction -------------------------------------------------------

def make_text_pdf(path, text):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), text, fontsize=24)
    doc.save(str(path))
    doc.close()


def make_image_only_pdf(path, text):
    """A PDF whose page is just a picture of the text, with no text layer (like your CS2208 outline)."""
    source = fitz.open()
    source.new_page().insert_text((72, 100), text, fontsize=24)
    pix = source[0].get_pixmap(dpi=200)
    source.close()

    out = fitz.open()
    page = out.new_page()
    page.insert_image(page.rect, pixmap=pix)
    out.save(str(path))
    out.close()


def tesseract_available():
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def test_extract_text_from_txt(tmp_path):
    path = tmp_path / "a.txt"
    path.write_bytes(TEXT)

    assert "domesticated mammals" in DocumentUtils().extract_text(path)


def test_extract_text_from_pdf_with_text_layer(tmp_path):
    path = tmp_path / "a.pdf"
    make_text_pdf(path, "Quarterly revenue grew")

    assert "Quarterly revenue" in DocumentUtils().extract_text(path)


@pytest.mark.skipif(not tesseract_available(), reason="Tesseract is not installed")
def test_extract_text_falls_back_to_ocr_for_image_only_pdf(tmp_path):
    path = tmp_path / "scan.pdf"
    make_image_only_pdf(path, "Quarterly revenue grew")

    text = DocumentUtils().extract_text(path)

    assert "revenue" in text.lower()


def test_chunk_text_respects_size_and_covers_the_text():
    text = "a" * 1200

    chunks = DocumentUtils().chunk_text(text, chunksize=500, overlap=50)

    assert len(chunks) >= 3
    assert max(len(c) for c in chunks) <= 500