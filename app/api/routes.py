from typing import List, Optional, Dict, Any, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession # New import
from fastapi_guard import SecurityDecorator # New import
from app.exceptions.custom_exceptions import AuthError # New import

from app.core.config import settings
from app.core.database import get_db_session # New import
from app.services.auth import authenticate_user, create_access_token, create_refresh_token, decode_token
from app.services.openrouter import openrouter_service
from app.models.database import User

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
    except Exception as e:
        raise AuthError(message="Could not validate credentials", details=str(e))

# Authentication endpoints
class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: LoginRequest, db_session: AsyncSession = Depends(get_db_session)):
    user = await authenticate_user(form_data.username, form_data.password, db_session)
    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}

@router.post("/refresh_token", response_model=Token)
async def refresh_access_token(refresh_token: str):
    try:
        payload = decode_token(refresh_token)
        username: str = payload.get("sub")
        if username is None:
            raise AuthError(message="Invalid refresh token")
        access_token = create_access_token(data={"sub": username})
        return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token} # Return new access token and original refresh token
    except ValueError as e:
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
async def create_chat_completion(request: ChatCompletionRequest, current_user: User = Depends(get_current_user)):
    messages_dict = [msg.dict() for msg in request.messages]
    if request.stream:
        async def generate_stream():
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
async def list_models():
    models = await openrouter_service.list_models()
    return models

# Background task functions
def process_long_task(data: str):
    # Simulate a long-running task
    import time
    time.sleep(10)
    print(f"Long task completed for data: {data}")

@router.post("/start-long-task")
async def start_long_task(data: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_long_task, data)
    return {"message": "Long task started in background"}