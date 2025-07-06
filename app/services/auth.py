from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings
from app.models.database import User
from app.core.database import get_db_session
from app.exceptions.custom_exceptions import AuthError # New import

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
    to_encode.update({"exp": expire, "iss": settings.jwt_issuer, "aud": settings.jwt_audience})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_expire_days)
    to_encode.update({"exp": expire, "iss": settings.jwt_issuer, "aud": settings.jwt_audience})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm], audience=settings.jwt_audience, issuer=settings.jwt_issuer)
        return payload
    except JWTError as e:
        raise AuthError(message="Could not validate credentials", details=str(e))

async def authenticate_user(username: str, password: str, db_session: AsyncSession) -> Optional[User]:
    # Fetch the user from the database
    result = await db_session.execute(select(User).filter(User.username == username))
    user = result.scalars().first()

    if not user:
        raise AuthError(message="Incorrect username or password")
    
    # Verify the password
    if not verify_password(password, user.password_hash):
        raise AuthError(message="Incorrect username or password")
        
    return user

# JWT Public/Private Key Management (for asymmetric algorithms like RS256)
# In a real application, these keys should be managed securely,
# e.g., fetched from AWS Secrets Manager, Google Secret Manager, HashiCorp Vault,
# or Kubernetes Secrets, and rotated regularly.
# For HS256 (symmetric), the SECRET_KEY from settings is used directly.

def get_jwt_public_key() -> str:
    """
    Retrieves the public key for JWT verification.
    For production, this should fetch a key from a secure key management system.
    """
    # TODO: Implement secure retrieval of the JWT public key.
    # Example: return some_key_management_service.get_public_key("jwt_public_key")
    raise NotImplementedError("JWT public key retrieval is not implemented. Use a secure key management system.")

def get_jwt_private_key() -> str:
    """
    Retrieves the private key for JWT signing.
    For production, this should fetch a key from a secure key management system.
    """
    # TODO: Implement secure retrieval of the JWT private key.
    # Example: return some_key_management_service.get_private_key("jwt_private_key")
    raise NotImplementedError("JWT private key retrieval is not implemented. Use a secure key management system.")