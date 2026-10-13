# Document Q&A

![CI](https://github.com/ATURKIEH/documentQa/actions/workflows/ci.yml/badge.svg)

Chat with your own documents. Create a chat, upload PDFs, Word or PowerPoint files, and ask questions. Answers come from the content of your files and cite the document they came from. A local LLM runs the whole thing, so nothing is sent to a third-party model API.

![Screenshot](docs/screenshot.png)

## Features

- **Retrieval-augmented answers** with a source pill showing which document each answer used
- **Multi-document chats:** documents are added to a chat after it is created with the `+` button
- **OCR fallback** for PDFs with no text layer (scanned pages, web pages printed to PDF)
- **Normal conversation too:** an intent classifier routes greetings and small talk to a chat reply instead of the document search
- **Auth:** signup and login with JWT access and refresh tokens, with automatic token refresh on the client
- **Redis caching** of repeated questions, with the cache invalidated when a chat's documents change
- **Graceful failures:** a clear 503 when the language model is unavailable
- Dark and light themes, relative timestamps, auto-scroll and empty states

## Architecture

```
Browser ──► nginx (React build, serves /)
              │
              └─ /api ──► FastAPI ──┬─► PostgreSQL   users, chats, messages, documents
                                    ├─► Redis        answer cache
                                    ├─► Pinecone     document chunk embeddings
                                    └─► Ollama       llama3.2:3b (answers + intent routing)
```

1. **Upload:** the file is parsed (PDF, DOCX or PPTX, with OCR when needed), split into 500-character chunks with 50 overlap, embedded and stored in Pinecone with `user_id` and `document_id` metadata.
2. **Question:** the question is classified as document or chat. For document questions, each document in the chat is queried separately (top 3 chunks each), the matches are merged by score, and the model answers using only that context.
3. **Answer:** the response is saved with its citations and cached in Redis for an hour.

## Tech stack

| Layer | Tools |
|---|---|
| Backend | Python 3.13, FastAPI, SQLAlchemy, Alembic, Pydantic v2 |
| LLM | Ollama (`llama3.2:3b`) through LangChain |
| Vector store | Pinecone |
| Data | PostgreSQL, Redis |
| OCR | PyMuPDF, Tesseract (`pytesseract`) |
| Frontend | React, TypeScript, Vite, Tailwind CSS v4 |
| Infra | Docker, Docker Compose, nginx, GitHub Actions, AWS EC2 |

## Run it locally

You need Docker, and a Pinecone account (index with the dimension of your embedding model).

1. Clone the repository and create a `.env` file in the project root (see Configuration below).
2. Start everything:
```bash
   docker compose up --build
```
3. Pull the model once. It is stored in a Docker volume, so this is a one-time step:
```bash
   docker compose exec ollama ollama pull llama3.2:3b
```
4. Open http://localhost:5173, create an account and start a chat.

The backend runs database migrations (`alembic upgrade head`) automatically on start. The API docs are at http://localhost:8000/docs.

> Do not use `docker compose down -v` unless you want to delete your database and the downloaded model, because `-v` removes the volumes.

### Configuration

Copy `.env.example` to `.env` and fill in the values: the database password, the JWT secret, and your Pinecone credentials. Compose sets the Postgres, Redis and Ollama hostnames for the containers, so those don't need to be in `.env`. Use `FRONTEND_PORT=80` on a server (the default is 5173).

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest --cov
```

59 tests cover auth, chats, documents, messages, caching and the RAG flow, with about 94% coverage. They use an in-memory SQLite database, a fake Redis and a fake LLM, so they need no running services. The OCR test needs Tesseract installed and is skipped without it. GitHub Actions runs the tests and builds both Docker images on every push.

## Deployment

The stack runs on a single AWS EC2 instance (t3.large, Ubuntu) with Docker Compose. nginx serves the frontend and proxies `/api` to the backend, so the browser only talks to one origin. Services use `restart: unless-stopped`, so the stack comes back on its own when the instance starts. Updating the server is `git pull && docker compose up -d --build`.

## Known limitations

- Retrieval works on meaning, so queries about a document's name ("the PDF called X") don't work well, and follow-up questions are not rewritten into standalone queries.
- A 3B model on CPU is slow, and the first answer after a restart takes longer while the model loads.
- No document removal from a chat, no upload size or type limits yet, and no rate limiting. Don't expose the app publicly without adding them.
- HTTP only in the current deployment (no domain or HTTPS).

## Project layout

```
backend/    FastAPI app, models, migrations, tests, Dockerfile
frontend/   React + TypeScript app, nginx config, Dockerfile
docker-compose.yml
.github/workflows/ci.yml
```