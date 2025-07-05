import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_read_users_me(client: AsyncClient, test_user):
    # Mock the get_current_user dependency
    with patch("app.api.routes.get_current_user", return_value=test_user):
        response = await client.get(
            "/api/v1/users/me",
            headers={
                "Authorization": "Bearer fake-token"
            }
        )
        assert response.status_code == 200
        assert response.json() == {"username": test_user.username, "email": test_user.email}

@pytest.mark.asyncio
async def test_create_chat_completion_non_stream(client: AsyncClient, test_user):
    mock_response_data = {"choices": [{"message": {"content": "Mocked response"}}]}
    with patch("app.api.routes.openrouter_service.generate_chat_completion", new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = mock_response_data
        with patch("app.api.routes.get_current_user", return_value=test_user):
            response = await client.post(
                "/api/v1/chat/completions",
                json={
                    "model": "test-model",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "stream": False
                },
                headers={
                    "Authorization": "Bearer fake-token"
                }
            )
            assert response.status_code == 200
            assert response.json() == mock_response_data
            mock_generate.assert_awaited_once_with(
                messages=[{"role": "user", "content": "Hello"}],
                model="test-model",
                stream=False,
                max_tokens=None,
                temperature=None,
                top_p=None
            )

@pytest.mark.asyncio
async def test_create_chat_completion_stream(client: AsyncClient, test_user):
    async def mock_stream_generator():
        yield "chunk1"
        yield "chunk2"

    with patch("app.api.routes.openrouter_service.generate_chat_completion", new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = mock_stream_generator()
        with patch("app.api.routes.get_current_user", return_value=test_user):
            response = await client.post(
                "/api/v1/chat/completions",
                json={
                    "model": "test-model",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "stream": True
                },
                headers={
                    "Authorization": "Bearer fake-token"
                }
            )
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream"
            content = ""
            async for chunk in response.aiter_bytes():
                content += chunk.decode()
            assert content == "chunk1chunk2"
            mock_generate.assert_awaited_once_with(
                messages=[{"role": "user", "content": "Hello"}],
                model="test-model",
                stream=True,
                max_tokens=None,
                temperature=None,
                top_p=None
            )

@pytest.mark.asyncio
async def test_list_models_api(client: AsyncClient):
    mock_models_data = [{"id": "model-1"}, {"id": "model-2"}]
    with patch("app.api.routes.openrouter_service.list_models", new_callable=AsyncMock) as mock_list_models:
        mock_list_models.return_value = mock_models_data
        response = await client.get("/api/v1/models")
        assert response.status_code == 200
        assert response.json() == mock_models_data
        mock_list_models.assert_awaited_once()

@pytest.mark.asyncio
async def test_start_long_task(client: AsyncClient):
    with patch("app.api.routes.process_long_task") as mock_process_long_task:
        response = await client.post(
            "/api/v1/start-long-task",
            params={
                "data": "test_data"
            }
        )
        assert response.status_code == 200
        assert response.json() == {"message": "Long task started in background"}
        mock_process_long_task.delay.assert_called_once_with("test_data")