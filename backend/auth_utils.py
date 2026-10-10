from passlib.context import CryptContext




class AuthUtils:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):

        if hasattr(self, '_initialized'):
            return
        else:
            self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated = 'auto')
            self._initialized = True

    def hash_password(self, password:str) -> str:
        password_bytes = password.encode('utf-8')[:72]
        truncated_password = password_bytes.decode('utf-8', errors='ignore')
        hashed_password = self.pwd_context.hash(truncated_password)
        return hashed_password

    def verify_password(self, plain_passwd:str, hashed_passwd:str)-> bool:
        password_bytes = plain_passwd.encode('utf-8')[:72]
        truncated_password = password_bytes.decode('utf-8', errors='ignore')
        return self.pwd_context.verify(truncated_password, hashed_passwd)

