import pytest
from httpx import AsyncClient
from app.services.auth import create_access_token, create_refresh_token, decode_token, verify_password, get_password_hash
from datetime import timedelta
from app.core.config import settings

@pytest.mark.asyncio
async def test_create_access_token():
    data = {"sub": "testuser"}
    token = create_access_token(data)
    assert isinstance(token, str)
    decoded = decode_token(token)
    assert decoded["sub"] == "testuser"
    assert "exp" in decoded

@pytest.mark.asyncio
async def test_create_access_token_with_expiry():
    data = {"sub": "testuser"}
    expires_delta = timedelta(minutes=1)
    token = create_access_token(data, expires_delta=expires_delta)
    decoded = decode_token(token)
    assert decoded["exp"] is not None

@pytest.mark.asyncio
async def test_create_refresh_token():
    data = {"sub": "testuser"}
    token = create_refresh_token(data)
    assert isinstance(token, str)
    decoded = decode_token(token)
    assert decoded["sub"] == "testuser"
    assert "exp" in decoded

@pytest.mark.asyncio
async def test_decode_token_invalid():
    with pytest.raises(ValueError, match="Could not validate credentials"):
        decode_token("invalid_token")

@pytest.mark.asyncio
async def test_password_hashing():
    password = "mysecretpassword"
    hashed_password = get_password_hash(password)
    assert verify_password(password, hashed_password)
    assert not verify_password("wrongpassword", hashed_password)

@pytest.mark.asyncio
async def test_login_endpoint(client: AsyncClient):
    # This test assumes a placeholder user in authenticate_user for now
    response = await client.post(
        "/api/v1/token",
        json={
            "username": "testuser",
            "password": "testpassword"
        }
    )
    assert response.status_code == 200
    json_response = response.json()
    assert "access_token" in json_response
    assert "refresh_token" in json_response
    assert json_response["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_endpoint_invalid_credentials(client: AsyncClient):
    response = await client.post(
        "/api/v1/token",
        json={
            "username": "wronguser",
            "password": "wrongpassword"
        }
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect username or password"}

@pytest.mark.asyncio
async def test_refresh_token_endpoint(client: AsyncClient):
    # First, get a token
    login_response = await client.post(
        "/api/v1/token",
        json={
            "username": "testuser",
            "password": "testpassword"
        }
    )
    refresh_token = login_response.json()["refresh_token"]

    # Then, use the refresh token
    refresh_response = await client.post(
        "/api/v1/refresh_token",
        params={
            "refresh_token": refresh_token
        }
    )
    assert refresh_response.status_code == 200
    json_response = refresh_response.json()
    assert "access_token" in json_response
    assert json_response["token_type"] == "bearer"
    assert json_response["refresh_token"] == refresh_token # Refresh token should be the same

@pytest.mark.asyncio
async def test_refresh_token_endpoint_invalid_token(client: AsyncClient):
    response = await client.post(
        "/api/v1/refresh_token",
        params={
            "refresh_token": "invalid_refresh_token"
        }
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}