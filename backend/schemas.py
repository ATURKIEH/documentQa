from pydantic import BaseModel
from datetime import datetime
from pydantic import EmailStr, Field

class UserCreate(BaseModel):
    email: EmailStr
    password : str = Field(..., min_length = 8)

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    created_at: datetime

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length = 8)

class RefreshRequest(BaseModel):
    refresh_token: str

class ChatCreate(BaseModel):
    document_ids: list[int] =[]
    title: str|None = None

class ChatResponse(BaseModel):
    id:int
    title:str
    documents: list[str]
    created_at: datetime
    updated_at: datetime

class CitationResponse(BaseModel):
    document: str

class MessageResponse(BaseModel):
    id:int
    role:str
    content:str
    created_at: datetime
    citations: list[CitationResponse]|None = None
    model_config = {"from_attributes": True}

class ChatDetailResponse(ChatResponse):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse]
    model_config = {"from_attributes": True}

class MessageCreate(BaseModel):
    content: str

class DocumentResponse(BaseModel):
    id: int
    filename: str
    model_config = {"from_attributes": True}