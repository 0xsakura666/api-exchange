import asyncio
from typing import Optional, Tuple

from models import APIKeyRecord, KeyStatus
from database import db
from config import get_settings


class KeyManager:
    def __init__(self):
        self.settings = get_settings()
        self._lock = asyncio.Lock()
        self._current_key: Optional[APIKeyRecord] = None
    
    async def get_key(self, min_balance: float = 0.01) -> Optional[APIKeyRecord]:
        """获取一个可用的 API Key"""
        async with self._lock:
            key = await db.get_available_key(min_balance)
            if key:
                self._current_key = key
            return key
    
    async def deduct_balance(self, key_id: int, amount: float):
        """扣除 Key 余额"""
        await db.deduct_balance(key_id, amount)
    
    async def mark_key_exhausted(self, key_id: int):
        """标记 Key 已耗尽"""
        await db.update_key_status(key_id, KeyStatus.EXHAUSTED)
    
    async def mark_key_invalid(self, key_id: int):
        """标记 Key 无效"""
        await db.update_key_status(key_id, KeyStatus.INVALID)
    
    async def get_model_price(self, model: str) -> float:
        """获取模型价格"""
        return await db.get_model_price(model)
    
    async def get_key_with_retry(self, model: str, max_retries: int = 3) -> Tuple[Optional[APIKeyRecord], float, int]:
        """
        获取可用 Key，根据模型价格判断余额是否足够
        返回 (key, price, retry_count)
        """
        price = await self.get_model_price(model)
        retries = 0
        
        while retries < max_retries:
            key = await self.get_key(min_balance=price)
            if key:
                return key, price, retries
            retries += 1
            await asyncio.sleep(0.1)
        
        return None, price, retries
    
    async def handle_request_error(self, key_id: int, error_message: str) -> bool:
        """
        处理请求错误，判断是否需要切换 Key
        返回 True 表示应该重试，False 表示不需要重试
        """
        error_lower = error_message.lower()
        
        exhausted_indicators = [
            "quota",
            "limit",
            "exceeded",
            "exhausted",
            "no remaining",
            "insufficient",
            "rate limit",
            "用完",
            "余额",
            "次数"
        ]
        
        invalid_indicators = [
            "invalid",
            "unauthorized",
            "authentication",
            "invalid api key",
            "invalid_api_key",
            "无效"
        ]
        
        for indicator in exhausted_indicators:
            if indicator in error_lower:
                await self.mark_key_exhausted(key_id)
                return True
        
        for indicator in invalid_indicators:
            if indicator in error_lower:
                await self.mark_key_invalid(key_id)
                return True
        
        return False
    
    async def import_keys(self, keys: list) -> dict:
        """
        批量导入 Keys
        keys: [(key_string, balance), ...]
        """
        result = {
            "total": len(keys),
            "added": 0,
            "duplicates": 0,
            "errors": 0
        }
        
        for key_str, balance in keys:
            try:
                record = await db.add_key(key_str, balance)
                if record:
                    result["added"] += 1
                else:
                    result["duplicates"] += 1
            except Exception:
                result["errors"] += 1
        
        return result
    
    async def get_stats(self):
        """获取统计信息"""
        return await db.get_stats()
    
    async def get_all_keys(self, status: Optional[str] = None):
        """获取所有 Keys"""
        return await db.get_all_keys(status)


key_manager = KeyManager()
