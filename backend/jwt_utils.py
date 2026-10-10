from fastapi import HTTPException, status
from jose import jwt
from datetime import datetime, timedelta, timezone
import random
import string
from jose import ExpiredSignatureError, JWTError
import os
from dotenv import load_dotenv
load_dotenv()

class JWTUtils:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        else:
            self.SECRET_KEY = os.getenv('JWT_SECRET_KEY')
            self.ALGORITHM = "HS256"
            self._initialized = True

    def create_access_token(self, data:dict, expires_delta: timedelta = None) -> str:
        dataN = data.copy()
        now = datetime.now(timezone.utc)
        if expires_delta is None:
            expiration = now + timedelta(minutes=15)
        else:
            expiration = now + expires_delta
        dataN.update({"exp": expiration})
        return jwt.encode(dataN, self.SECRET_KEY, algorithm = self.ALGORITHM)


    def create_refresh_token(self, data:dict)-> str:
        dataN = data.copy()
        now = datetime.now()
        expiration = now + timedelta(days=7)
        dataN.update({"exp": expiration})
        return jwt.encode(dataN, self.SECRET_KEY, algorithm = self.ALGORITHM)


    def decode_access_token(self, token: str) -> dict:
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            return payload
        except ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="The access token is expired."
            )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="The access token is invalid, malformed, or wrong."
            )

