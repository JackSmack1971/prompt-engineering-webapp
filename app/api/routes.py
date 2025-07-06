from typing import List, Optional, Dict, Any, AsyncGenerator
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request # Import Request
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, ValidationError, Field # Import Field for validation
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi_guard import SecurityDecorator
from app.exceptions.custom_exceptions import AuthError

from app.core.config import settings
from app.core.database import get_db_session
from app.services.auth import authenticate_user, create_access_token, create_refresh_token, decode_token
from app.services.openrouter import OpenRouterService
from app.models.database import User, AuditLog # Import AuditLog
from app.main import get_openrouter_service

from app.core.config import settings
from app.core.database import get_db_session
from app.services.auth import authenticate_user, create_access_token, create_refresh_token, decode_token
from app.services.openrouter import OpenRouterService # Import the class
from app.models.database import User
from app.main import get_openrouter_service # Import the dependency

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Dependency to get current user
from sqlalchemy import select # Add this import

# Dependency to get current user
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db_session: AsyncSession = Depends(get_db_session)
) -> User:
    try:
        payload = decode_token(token)
        username: str = payload.get("sub")
        if username is None:
            raise AuthError(message="Invalid authentication credentials")
        
        # Properly fetch user from database
        result = await db_session.execute(select(User).filter(User.username == username))
        user = result.scalars().first()
        
        if not user:
            raise AuthError(message="User not found")
            
        return user
    except (JWTError, ValidationError) as e:
        raise AuthError(message="Could not validate credentials", details=str(e))

# Authentication endpoints
class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=100) # Enforce stronger password requirements

class Message(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$") # Restrict roles to known values
    content: str = Field(..., min_length=1, max_length=settings.max_prompt_length) # Use setting for max length

class ChatCompletionRequest(BaseModel):
    model: str = Field("openai/gpt-3.5-turbo")
    messages: List[Message] = Field(..., min_items=1) # Ensure at least one message
    max_tokens: Optional[int] = Field(None, ge=1, le=settings.max_tokens_per_request) # Respect max_tokens_per_request setting
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0) # Common temperature range
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0) # Common top_p range
    stream: bool = False

@router.post("/token", response_model=Token)
async def login_for_access_token(
    request: Request, # Inject Request object
    form_data: LoginRequest,
    db_session: AsyncSession = Depends(get_db_session)
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")

    try:
        user = await authenticate_user(form_data.username, form_data.password, db_session)
        access_token = create_access_token(data={"sub": user.username})
        refresh_token = create_refresh_token(data={"sub": user.username})

        # Log successful login
        audit_log = AuditLog(
            user_id=user.id,
            action="user_login_success",
            entity_type="User",
            entity_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db_session.add(audit_log)
        await db_session.commit()
        await db_session.refresh(audit_log)

        return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}
    except AuthError as e:
        # Log failed login attempt
        audit_log = AuditLog(
            user_id=None, # User ID is not known for failed login
            action="user_login_failure",
            entity_type="User",
            description=f"Login attempt for username: {form_data.username}",
            ip_address=ip_address,
            user_agent=user_agent
        )
        db_session.add(audit_log)
        await db_session.commit()
        await db_session.refresh(audit_log)
        raise e

@router.post("/refresh_token", response_model=Token)
async def refresh_access_token(refresh_token: str):
    try:
        payload = decode_token(refresh_token)
        username: str = payload.get("sub")
        if username is None:
            raise AuthError(message="Invalid refresh token")
        access_token = create_access_token(data={"sub": username})
        return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token} # Return new access token and original refresh token
    except (JWTError, ValidationError) as e: # Catch JWTError and ValidationError directly
        raise AuthError(message="Could not refresh token", details=str(e))

# User endpoints
@router.get(
    "/users/me",
    dependencies=[Depends(get_current_user)],
    security_decorators=[SecurityDecorator(requests=settings.rate_limit_user_requests, window=settings.rate_limit_user_window)]
)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "email": current_user.email}

# LLM Generation endpoints
class Message(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str = "openai/gpt-3.5-turbo"
    messages: List[Message]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    stream: bool = False

@router.post(
    "/chat/completions",
    dependencies=[Depends(get_current_user)],
    security_decorators=[SecurityDecorator(requests=settings.rate_limit_llm_requests, window=settings.rate_limit_llm_window)]
)
async def create_chat_completion(
    request: ChatCompletionRequest,
    current_user: User = Depends(get_current_user),
    openrouter_service: OpenRouterService = Depends(get_openrouter_service) # Inject OpenRouterService
) -> StreamingResponse | Dict[str, Any]:
    messages_dict: List[Dict[str, str]] = [msg.dict() for msg in request.messages]
    if request.stream:
        async def generate_stream() -> AsyncGenerator[str, None]:
            async for chunk in openrouter_service.generate_chat_completion(
                messages=messages_dict,
                model=request.model,
                stream=True,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p
            ):
                yield chunk
        return StreamingResponse(generate_stream(), media_type="text/event-stream")
    else:
        response = await openrouter_service.generate_chat_completion(
            messages=messages_dict,
            model=request.model,
            stream=False,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p
        )
        return response

# Models endpoint
@router.get("/models")
async def list_models(openrouter_service: OpenRouterService = Depends(get_openrouter_service)): # Inject OpenRouterService
    models = await openrouter_service.list_models()
    return models

# Background task functions
async def process_long_task(data: str):
    # Simulate a long-running task
    await asyncio.sleep(10)
    print(f"Long task completed for data: {data}")

@router.post("/start-long-task")
async def start_long_task(
    data: str = Field(..., min_length=1, max_length=1000), # Add validation for data length
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    background_tasks.add_task(process_long_task, data)
    return {"message": "Long task started in background"}