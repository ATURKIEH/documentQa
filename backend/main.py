import os
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Chat, Document, Message, User, ChatDocument
from schemas import ChatDetailResponse, MessageCreate, UserCreate, UserResponse, Token, RefreshRequest, ChatResponse, MessageResponse, ChatCreate, DocumentResponse
from auth_utils import AuthUtils
from jwt_utils import JWTUtils
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from embed_utils import EmbedUtils
from document_utils import DocumentUtils
from pinecone import Pinecone
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import redis
from fastapi.middleware.cors import CORSMiddleware
import json, httpx
from sqlalchemy import func

load_dotenv()
app = FastAPI()
document_utils = DocumentUtils()
embed_utils = EmbedUtils()
r = redis.Redis(host='localhost', port=6379, decode_responses=True)




def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def to_chat_response(chat: Chat) -> ChatResponse:
    return ChatResponse(
        id=chat.id,
        title=chat.title,
        documents=list(dict.fromkeys(link.document.filename for link in chat.document_links)),
        created_at=chat.created_at,
        updated_at=chat.updated_at,
    )

def ollama_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="The language model is unavailable. Please try again shortly.",
    )

def classify_intent(question: str) -> str:
    llm = ChatOllama(model="llama3.2:3b", temperature=0, num_predict=4)
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You route messages in a document Q&A app. Reply with exactly one word.\n"
         "DOCS: the message asks about, summarizes, or refers to the content of the user's documents "
         "(facts, names, dates, topics, 'the document', 'the pdf', 'the file').\n"
         "CHAT: greetings, small talk, thanks, or questions about you the assistant.\n"
         "If unsure, reply DOCS."),
        ("human", "{question}"),
    ])
    try:
        out = (prompt | llm).invoke({"question": question}).content.strip().upper()
    except (httpx.ConnectError, ConnectionError):
        raise ollama_unavailable()
    return "CHAT" if out.startswith("CHAT") else "DOCS"

def generate_chat_reply(question: str, history: list) -> dict:
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a friendly assistant inside a document Q&A app. Chat naturally and keep replies short. "
         "If the user wants information from their documents, invite them to ask a specific question about the content."),
        MessagesPlaceholder("history"),
        ("human", "{question}"),
    ])
    llm = ChatOllama(model="llama3.2:3b", temperature=0.7)
    history_msgs = [(m.role, m.content) for m in history]
    try:
        response = (prompt | llm).invoke({"history": history_msgs, "question": question})
    except (httpx.ConnectError, ConnectionError):
        raise ollama_unavailable()
    return {"content": response.content, "citations": [], "cacheable": False}

@app.post('/auth/signup', response_model = UserResponse)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()

    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail= "User Already Exists."
        )
    else:
        authutils = AuthUtils()
        hashed_password = authutils.hash_password(user.password)
        db_user = User(email = user.email, hashed_password = hashed_password)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

@app.post('/auth/login', response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == form_data.username).first()

    authutils = AuthUtils()

    if db_user is None or not authutils.verify_password(form_data.password, db_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Incorrect email or password.'
        )

    data = {'sub': str(db_user.id)}
    jwt_utils = JWTUtils()
    access_token = jwt_utils.create_access_token(data=data)
    refresh_token = jwt_utils.create_refresh_token(data=data)
    return {'access_token': str(access_token), 'refresh_token': str(refresh_token),  'token_type': 'bearer'}

@app.post('/auth/refresh', response_model=Token)
def refresh(request: RefreshRequest, db: Session = Depends(get_db)):
    jwt_utils = JWTUtils()
    payload = jwt_utils.decode_access_token(request.refresh_token)
    user_id = int(payload['sub'])
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail = 'User deleted after token was issued.'
            )

    data = {'sub': str(db_user.id)}
    new_access_token = jwt_utils.create_access_token(data=data)
    new_refresh_token = jwt_utils.create_refresh_token(data=data)
    return {'access_token': str(new_access_token), 'refresh_token': str(new_refresh_token),  'token_type': 'bearer'}


oauth2_scheme = OAuth2PasswordBearer(tokenUrl='auth/login')

def get_current_user(token:str = Depends(oauth2_scheme), db:Session = Depends(get_db)) -> User:
    jwt_utils = JWTUtils()
    payload = jwt_utils.decode_access_token(token)
    user_id = int(payload['sub'])
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail = 'User deleted after token was issued.'
        )
    return db_user

@app.get('/auth/me', response_model = UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@app.post('/documents/upload')
async def upload_document(file: UploadFile = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file uploaded."
        )
    upload_directory = Path(f"uploaded_files/{current_user.id}")
    upload_directory.mkdir(parents=True, exist_ok=True)
    temp_file_path = upload_directory / file.filename
    file_content = await file.read()
    with open(temp_file_path, "wb") as f:
        f.write(file_content)
    new_document = Document(
        user_id=current_user.id,
        filename=file.filename,
        pinecone_namespace=f"user_{current_user.id}"
    )
    db.add(new_document)
    db.commit()
    db.refresh(new_document)

    document_id = new_document.id
    extracted_text = document_utils.extract_text(temp_file_path)
    if not extracted_text.strip():
        db.delete(new_document)
        db.commit()
        os.remove(temp_file_path)
        raise HTTPException(status_code=422, detail="No text could be extracted from this file.")
    extracted_chunks = document_utils.chunk_text(extracted_text, chunksize=500, overlap=50)
    embed_utils.store_document_chunks(extracted_chunks, user_id=current_user.id, document_id=document_id)
    os.remove(temp_file_path)
    return {
        "message": "Document uploaded successfully",
        "document_id": document_id,
        "filename": file.filename,
        "chunks_stored": len(extracted_chunks)
    }

@app.post('/chats', response_model=ChatResponse)
def create_chat(chat: ChatCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    documents = []
    for document_id in chat.document_ids:
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.user_id == current_user.id
        ).first()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found for the current user."
            )
        documents.append(document)


    new_chat = Chat(
        user_id=current_user.id,
        title=chat.title or "New Chat"
    )
    db.add(new_chat)
    db.commit()
    db.refresh(new_chat)
    for document in documents:
        chat_document = ChatDocument(chat_id=new_chat.id, document_id=document.id)
        db.add(chat_document)
    db.commit()

    return to_chat_response(new_chat)


@app.get('/chats', response_model=list[ChatResponse])
def get_chats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db))-> list[ChatResponse]:
    chats = db.query(Chat).filter(Chat.user_id == current_user.id).order_by(Chat.updated_at.desc()).all()
    result = []
    for chat in chats:
        document_names = [link.document.filename for link in chat.document_links]
        ChatResponseModel = ChatResponse(
            id=chat.id,
            title=chat.title,
            documents=document_names,
            created_at=chat.created_at,
            updated_at=chat.updated_at
        )
        result.append(ChatResponseModel)
        

    return result

@app.get('/chats/{chat_id}', response_model=ChatDetailResponse)
def get_chat(chat_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ChatDetailResponse:
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id).first()
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat with ID {chat_id} not found for the current user."
        )
    document_names = [link.document.filename for link in chat.document_links]
    return ChatDetailResponse(
        id=chat.id,
        title=chat.title,
        documents=document_names,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        messages=chat.messages
    )


NO_MATCH_ANSWER = "I don't have information on that in this document."

def generate_answer(question: str, user_id: int, document_ids: list[int], db: Session, history:list) -> dict:
    if classify_intent(question) == "CHAT":
        return generate_chat_reply(question, history)

    embedded_question = embed_utils.embeddings.embed_query(question)
    matches = []
    for doc_id in set(document_ids):
        res = embed_utils.index.query(
            vector=embedded_question,
            top_k=3,
            filter={"user_id": user_id, "document_id": doc_id},
            include_metadata=True,
        )
        matches.extend(res["matches"])
    matches.sort(key=lambda m: m["score"], reverse=True)
    if not matches:
        return {"content": NO_MATCH_ANSWER, "citations": [], "cacheable": False}

    context = "\n\n".join(m["metadata"]["text"] for m in matches)

    prompt_template = ChatPromptTemplate.from_messages([
        ("system",
         "You are a document assistant. Answer using ONLY the provided context. "
         "Do not add facts, definitions, or acronym expansions that are not written in the context. "
         "If the context does not contain the answer, reply exactly: "
         "I don't have information on that in this document."),
        ("human", "Context:\n{context}\n\nQuestion: {question}"),
    ])
    llm = ChatOllama(model="llama3.2:3b", temperature=0)
    try:
        response = (prompt_template | llm).invoke({"context": context, "question": question})
    except (httpx.ConnectError, ConnectionError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The language model is unavailable. Please try again shortly.",
        )

    # Pinecone returns numeric metadata as floats, so cast back to int
    doc_ids = {int(m["metadata"]["document_id"]) for m in matches}
    docs = db.query(Document).filter(Document.id.in_(doc_ids), Document.user_id == user_id).all()
    citations = [{"document": d.filename} for d in docs]
    return {"content": response.content, "citations": citations, "cacheable": True}


@app.post('/chats/{chat_id}/messages', response_model=MessageResponse)
def send_message(chat_id: int, message: MessageCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id).first()
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat with ID {chat_id} not found for the current user.")

    document_ids = [
        link.document_id
        for link in db.query(ChatDocument).filter(ChatDocument.chat_id == chat.id).all()
    ]
    if not document_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This chat has no documents scoped to it.")
    doc_key = "-".join(str(i) for i in sorted(document_ids))
    cache_key = f"chat:v3:{chat_id}:{doc_key}:question:{message.content}"
    cached = r.get(cache_key)
    if cached:
        payload = json.loads(cached)
    else:
        history = (
            db.query(Message)
            .filter(Message.chat_id == chat.id)
            .order_by(Message.id.desc())
            .limit(6)
            .all()
        )[::-1]
        payload = generate_answer(message.content, current_user.id, document_ids, db, history)
        if payload["cacheable"]:
            r.set(cache_key, json.dumps(payload), ex=3600)

    db.add(Message(chat_id=chat.id, role="user", content=message.content))
    db.commit()
    chat.updated_at = func.now()
    assistant_message = Message(
        chat_id=chat.id,
        role="assistant",
        content=payload["content"],
        citations=payload["citations"],
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)
    return assistant_message
    


@app.delete('/chats/{chat_id}')
def delete_chat(chat_id: int, current_user: User = Depends(get_current_user), db : Session = Depends(get_db)):
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id).first()
    if not chat:
        raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Chat with ID {chat_id} not found for the current user."
                )

    db.delete(chat)
    db.commit()
    return {'message': 'Successful deletion of chat'}

@app.get('/documents', response_model=list[DocumentResponse])
def list_documents(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(Document)
        .filter(Document.user_id == current_user.id)
        .order_by(Document.id.desc())
        .all()
    )

@app.post('/chats/{chat_id}/documents', response_model=ChatResponse)
async def upload_document_to_chat(
    chat_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id).first()
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat with ID {chat_id} not found for the current user.")

    result = await upload_document(file=file, current_user=current_user, db=db)
    print("UPLOAD RESULT:", result)

    if result["chunks_stored"] == 0:
        raise HTTPException(status_code=422, detail="No text could be extracted from this file.")

    new_document_id = result["document_id"]
    db.add(ChatDocument(chat_id=chat.id, document_id=new_document_id))

    chat.updated_at = func.now()
    db.commit()
    db.refresh(chat)
    return to_chat_response(chat)

                                               

    


