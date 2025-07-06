import pytest
from typing import AsyncGenerator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.config import settings
from app.core.database import get_db_session # New import
from app.models.database import Base, User, Prompt, TestResult

# Create test engine with SQLite
TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5433/test_db"

@pytest.fixture(name="async_engine", scope="session")
async def async_engine_fixture():
    engine = create_async_engine(TEST_DATABASE_URL, echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(name="async_session", scope="function")
async def async_session_fixture(async_engine) -> AsyncGenerator[AsyncSession, None]:
    async_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session_maker() as session:
        yield session

@pytest.fixture(name="client", scope="function")
async def client_fixture(async_session) -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_db_session] = lambda: async_session
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides = {}

@pytest.fixture(name="test_user")
async def test_user_fixture(async_session: AsyncSession) -> User:
    user = User(username="testuser", email="test@example.com", password_hash="hashedpassword")
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)
    return user

@pytest.fixture(name="test_prompt")
async def test_prompt_fixture(async_session: AsyncSession, test_user: User) -> Prompt:
    prompt = Prompt(user_id=test_user.id, title="Test Prompt", content="This is a test prompt.")
    async_session.add(prompt)
    await async_session.commit()
    await async_session.refresh(prompt)
    return prompt

@pytest.fixture(name="test_test_result")
async def test_test_result_fixture(async_session: AsyncSession, test_user: User, test_prompt: Prompt) -> TestResult:
    test_result = TestResult(
        user_id=test_user.id,
        prompt_id=test_prompt.id,
        model_name="gpt-3.5-turbo",
        test_input="Hello world",
        test_output="Hello back"
    )
    async_session.add(test_result)
    await async_session.commit()
    await async_session.refresh(test_result)
    return test_result