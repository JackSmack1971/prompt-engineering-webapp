from datetime import datetime, timedelta
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings
from app.models.database import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_expire_minutes)
    to_encode.update({"exp": expire, "sub": settings.jwt_issuer, "aud": settings.jwt_audience})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_expire_days)
    to_encode.update({"exp": expire, "sub": settings.jwt_issuer, "aud": settings.jwt_audience})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm], audience=settings.jwt_audience, issuer=settings.jwt_issuer)
        return payload
    except JWTError as e:
        raise ValueError("Could not validate credentials") from e

async def authenticate_user(username: str, password: str) -> Optional[User]:
    # This is a placeholder. In a real app, you'd fetch the user from the DB
    # and verify their password.
    if username == "testuser" and password == "testpassword": # Example hardcoded user
        user = User(username="testuser", email="test@example.com", password_hash=get_password_hash("testpassword"))
        return user
    return None

# Placeholder for JWT public/private key management
# In a real application, you would manage these securely, e.g., AWS Secrets Manager
def get_jwt_public_key() -> str:
    # This is a placeholder. Replace with actual public key retrieval.
    return "" # Your public key here

def get_jwt_private_key() -> str:
    # This is a placeholder. Replace with actual private key retrieval.
    return "" # Your private key here