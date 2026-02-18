import httpx
import json
import asyncio
from typing import AsyncGenerator, Optional
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from models import ChatCompletionRequest, APIKeyRecord
from config import get_settings
from key_manager import key_manager
from database import db


class APIProxy:
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.upstream_base_url.rstrip("/")
    
    async def _make_request(
        self,
        key: APIKeyRecord,
        request: ChatCompletionRequest,
        stream: bool = False
    ) -> httpx.Response:
        """发送请求到上游 API"""
        headers = {
            "Authorization": f"Bearer {key.key}",
            "Content-Type": "application/json"
        }
        
        payload = request.model_dump(exclude_none=True)
        payload["stream"] = stream
        
        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            if stream:
                return await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=None
                )
            else:
                return await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
    
    async def _stream_response(
        self,
        key: APIKeyRecord,
        request: ChatCompletionRequest,
        price: float
    ) -> AsyncGenerator[bytes, None]:
        """处理流式响应"""
        headers = {
            "Authorization": f"Bearer {key.key}",
            "Content-Type": "application/json"
        }
        
        payload = request.model_dump(exclude_none=True)
        payload["stream"] = True
        
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        error_text = error_body.decode("utf-8")
                        
                        should_retry = await key_manager.handle_request_error(
                            key.id, error_text
                        )
                        
                        if should_retry:
                            new_key, new_price, _ = await key_manager.get_key_with_retry(request.model)
                            if new_key:
                                async for chunk in self._stream_response(new_key, request, new_price):
                                    yield chunk
                                return
                        
                        yield f"data: {json.dumps({'error': error_text})}\n\n".encode()
                        return
                    
                    await key_manager.deduct_balance(key.id, price)
                    
                    async for chunk in response.aiter_bytes():
                        yield chunk
                        
        except httpx.TimeoutException:
            yield f"data: {json.dumps({'error': 'Request timeout'})}\n\n".encode()
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n".encode()
    
    async def chat_completions(
        self,
        request: ChatCompletionRequest,
        max_retries: int = 3
    ):
        """处理 Chat Completions 请求"""
        key, price, _ = await key_manager.get_key_with_retry(request.model, max_retries)
        
        if not key:
            raise HTTPException(
                status_code=503,
                detail=f"No available API keys with sufficient balance (need ${price:.2f}). Please add more keys."
            )
        
        if request.stream:
            return StreamingResponse(
                self._stream_response(key, request, price),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
        
        retries = 0
        current_key = key
        current_price = price
        
        while retries < max_retries:
            try:
                response = await self._make_request(current_key, request, stream=False)
                
                if response.status_code == 200:
                    await key_manager.deduct_balance(current_key.id, current_price)
                    return response.json()
                
                error_text = response.text
                should_retry = await key_manager.handle_request_error(
                    current_key.id, error_text
                )
                
                if should_retry:
                    current_key, current_price, _ = await key_manager.get_key_with_retry(request.model)
                    if not current_key:
                        raise HTTPException(
                            status_code=503,
                            detail="All API keys exhausted"
                        )
                    retries += 1
                    continue
                
                raise HTTPException(
                    status_code=response.status_code,
                    detail=error_text
                )
                
            except httpx.TimeoutException:
                raise HTTPException(
                    status_code=504,
                    detail="Request to upstream API timed out"
                )
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Internal error: {str(e)}"
                )
        
        raise HTTPException(
            status_code=503,
            detail="Max retries exceeded"
        )
    
    async def list_models(self):
        """获取可用模型列表"""
        key = await key_manager.get_key()
        
        if not key:
            return {
                "object": "list",
                "data": []
            }
        
        try:
            headers = {
                "Authorization": f"Bearer {key.key}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers=headers
                )
                
                if response.status_code == 200:
                    return response.json()
                
                return {
                    "object": "list",
                    "data": [
                        {
                            "id": "gemini-3-pro-preview-y",
                            "object": "model",
                            "created": 1700000000,
                            "owned_by": "api-exchange"
                        }
                    ]
                }
        except Exception:
            return {
                "object": "list",
                "data": []
            }


api_proxy = APIProxy()
