import httpx
import json
from typing import AsyncGenerator, Dict, Any, List, Optional
from fastapi import status # Import status for HTTP status codes
from app.exceptions.custom_exceptions import APIException # Ensure APIException is imported

from app.core.config import settings

class OpenRouterService:
    def __init__(self):
        self.base_url = settings.openrouter_base_url
        self.api_key = settings.openrouter_api_key.get_secret_value()
        self.timeout = settings.openrouter_timeout

    async def _make_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.request(method, url, headers=headers, **kwargs)
                response.raise_for_status()  # Raise an exception for 4xx/5xx responses
                return response
            except httpx.TimeoutException:
                raise APIException(
                    status_code=status.HTTP_408_REQUEST_TIMEOUT,
                    code="OPENROUTER_TIMEOUT",
                    message="Request to OpenRouter API timed out.",
                    details={"url": url}
                )
            except httpx.ConnectError:
                raise APIException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    code="OPENROUTER_CONNECTION_ERROR",
                    message="Could not connect to OpenRouter API.",
                    details={"url": url}
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                    raise APIException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        code="OPENROUTER_RATE_LIMITED",
                        message="OpenRouter API rate limit exceeded. Please try again later.",
                        details={"retry_after": e.response.headers.get("Retry-After")}
                    )
                elif e.response.status_code == status.HTTP_401_UNAUTHORIZED:
                    raise APIException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        code="OPENROUTER_UNAUTHORIZED",
                        message="Invalid OpenRouter API key.",
                        details={"url": url}
                    )
                elif e.response.status_code == status.HTTP_404_NOT_FOUND:
                    raise APIException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        code="OPENROUTER_NOT_FOUND",
                        message="OpenRouter API endpoint or model not found.",
                        details={"url": url}
                    )
                else:
                    raise APIException(
                        status_code=e.response.status_code,
                        code=f"OPENROUTER_HTTP_ERROR_{e.response.status_code}",
                        message=f"OpenRouter API returned an HTTP error: {e.response.status_code}",
                        details={"url": url, "response": e.response.text}
                    ) from e

    async def list_models(self) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/models"
        response = await self._make_request("GET", url)
        return response.json().get('data', [])

    async def _generate_chat_completion_internal(self, messages: List[Dict[str, str]], model: str, stream: bool, **kwargs):
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            **kwargs
        }
        response = await self._make_request("POST", url, json=payload)
        return response

    async def generate_chat_completion(self, messages: List[Dict[str, str]], model: str = "openai/gpt-3.5-turbo", **kwargs) -> Dict[str, Any]:
        response = await self._generate_chat_completion_internal(messages, model, False, **kwargs)
        return response.json()

    async def generate_chat_completion_stream(self, messages: List[Dict[str, str]], model: str = "openai/gpt-3.5-turbo", **kwargs) -> AsyncGenerator[str, None]:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            **kwargs
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", url, headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }, json=payload) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    # OpenRouter sends data in SSE format
                    decoded_chunk = chunk.decode('utf-8')
                    for line in decoded_chunk.splitlines():
                        if line.startswith("data:"):
                            json_data = line[len("data:"):].strip()
                            if json_data == "[DONE]":
                                continue
                            try:
                                data = json.loads(json_data)
                                if 'choices' in data and len(data['choices']) > 0:
                                    delta = data['choices'][0].get('delta', {})
                                    if 'content' in delta:
                                        yield delta['content']
                            except json.JSONDecodeError:
                                # Handle cases where a line might not be complete JSON
                                continue

    async def get_model_info(self, model_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/models/{model_id}"
        try:
            response = await self._make_request("GET", url)
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

openrouter_service = OpenRouterService()