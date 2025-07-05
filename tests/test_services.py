import pytest
from unittest.mock import AsyncMock, patch
from app.services.openrouter import OpenRouterService
from app.services.cache import CacheService
from app.core.config import settings
import httpx
import json

@pytest.fixture
def openrouter_service_instance():
    return OpenRouterService()

@pytest.mark.asyncio
async def test_list_models(openrouter_service_instance):
    mock_response_data = {"data": [{"id": "model-1"}, {"id": "model-2"}]}
    with patch('httpx.AsyncClient.request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value.json.return_value = mock_response_data
        mock_request.return_value.raise_for_status.return_value = None
        
        models = await openrouter_service_instance.list_models()
        assert models == mock_response_data['data']
        mock_request.assert_awaited_once_with("GET", f"{settings.openrouter_base_url}/models", headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json"
        })

@pytest.mark.asyncio
async def test_generate_chat_completion_non_stream(openrouter_service_instance):
    mock_response_data = {"choices": [{"message": {"content": "Hello"}}]}
    with patch('httpx.AsyncClient.request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value.json.return_value = mock_response_data
        mock_request.return_value.raise_for_status.return_value = None

        messages = [{"role": "user", "content": "Hi"}]
        response = await openrouter_service_instance.generate_chat_completion(messages=messages, stream=False)
        assert response == mock_response_data

@pytest.mark.asyncio
async def test_generate_chat_completion_stream(openrouter_service_instance):
    async def mock_aiter_bytes():
        yield b'data: {"choices":[{"delta":{"content":"Hello"}}]}' + b'\n\n'
        yield b'data: {"choices":[{"delta":{"content":" world"}}]}' + b'\n\n'
        yield b'data: [DONE]' + b'\n\n'

    mock_response = AsyncMock()
    mock_response.aiter_bytes.return_value = mock_aiter_bytes()
    mock_response.raise_for_status.return_value = None

    with patch('httpx.AsyncClient.stream', return_value=mock_response):
        messages = [{"role": "user", "content": "Hi"}]
        stream_generator = openrouter_service_instance.generate_chat_completion(messages=messages, stream=True)
        
        chunks = [chunk async for chunk in stream_generator]
        assert chunks == ["Hello", " world"]

@pytest.mark.asyncio
async def test_get_model_info(openrouter_service_instance):
    mock_response_data = {"id": "model-1", "name": "Model One"}
    with patch('httpx.AsyncClient.request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value.json.return_value = mock_response_data
        mock_request.return_value.raise_for_status.return_value = None

        model_info = await openrouter_service_instance.get_model_info("model-1")
        assert model_info == mock_response_data

@pytest.mark.asyncio
async def test_get_model_info_not_found(openrouter_service_instance):
    with patch('httpx.AsyncClient.request', new_callable=AsyncMock) as mock_request:
        mock_response = httpx.Response(404, request=httpx.Request("GET", "http://test"))
        mock_response.raise_for_status = lambda: mock_response.read()
        mock_request.return_value = mock_response

        model_info = await openrouter_service_instance.get_model_info("non-existent-model")
        assert model_info is None

@pytest.fixture
async def cache_service_instance():
    # Use a real redis client for integration testing, but connect to a test database
    # or mock it if a real Redis instance is not available during testing.
    # For this example, we'll mock it for simplicity.
    service = CacheService()
    service.redis_client = AsyncMock()
    return service

@pytest.mark.asyncio
async def test_cache_set_get(cache_service_instance):
    key = "test_key"
    value = {"data": "test_value"}
    await cache_service_instance.set(key, value)
    cache_service_instance.redis_client.set.assert_awaited_once_with(key, json.dumps(value), ex=None)

    cache_service_instance.redis_client.get.return_value = json.dumps(value)
    retrieved_value = await cache_service_instance.get(key)
    assert retrieved_value == value

@pytest.mark.asyncio
async def test_cache_delete(cache_service_instance):
    key = "test_key"
    await cache_service_instance.delete(key)
    cache_service_instance.redis_client.delete.assert_awaited_once_with(key)

@pytest.mark.asyncio
async def test_cache_increment(cache_service_instance):
    key = "counter"
    cache_service_instance.redis_client.incr.return_value = 1
    result = await cache_service_instance.increment(key)
    assert result == 1
    cache_service_instance.redis_client.incr.assert_awaited_once_with(key, 1)

@pytest.mark.asyncio
async def test_cache_cached_decorator(cache_service_instance):
    @cache_service_instance.cached("test_prefix")
    async def my_test_function(arg1, arg2):
        return arg1 + arg2

    # First call, should not be in cache
    cache_service_instance.redis_client.get.return_value = None
    cache_service_instance.redis_client.set.return_value = None
    result1 = await my_test_function(1, 2)
    assert result1 == 3
    cache_service_instance.redis_client.get.assert_awaited_once() # Called once
    cache_service_instance.redis_client.set.assert_awaited_once() # Called once

    # Second call, should be in cache
    cache_service_instance.redis_client.get.reset_mock()
    cache_service_instance.redis_client.set.reset_mock()
    cache_service_instance.redis_client.get.return_value = json.dumps(3)
    result2 = await my_test_function(1, 2)
    assert result2 == 3
    cache_service_instance.redis_client.get.assert_awaited_once() # Called once
    cache_service_instance.redis_client.set.assert_not_awaited() # Not called