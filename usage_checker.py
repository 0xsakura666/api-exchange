import httpx
import asyncio
from typing import Optional, List

from models import UsageCheckResponse, APIKeyRecord
from config import get_settings
from database import db


class UsageChecker:
    def __init__(self):
        self.settings = get_settings()
        self.upstream_base = self.settings.upstream_base_url.rstrip("/").replace("/v1", "")
    
    async def check_single_key(self, key: str) -> UsageCheckResponse:
        """查询单个 Key 的余额（通过 billing API）"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {"Authorization": f"Bearer {key}"}
                
                # 获取总额度
                sub_response = await client.get(
                    f"{self.upstream_base}/dashboard/billing/subscription",
                    headers=headers
                )
                
                # 获取已用额度
                usage_response = await client.get(
                    f"{self.upstream_base}/dashboard/billing/usage",
                    headers=headers
                )
                
                if sub_response.status_code == 200 and usage_response.status_code == 200:
                    sub_data = sub_response.json()
                    usage_data = usage_response.json()
                    
                    total = sub_data.get("hard_limit_usd") or sub_data.get("soft_limit_usd") or 0
                    # total_usage 单位是 0.01，需要除以 100
                    used = (usage_data.get("total_usage") or 0) / 100.0
                    remaining = total - used
                    
                    return UsageCheckResponse(
                        key=key,
                        remaining=remaining,
                        used=used,
                        total=total,
                        valid=True
                    )
                
                # 只有 401 才是真正无效的 Key
                if sub_response.status_code == 401 or usage_response.status_code == 401:
                    return UsageCheckResponse(
                        key=key,
                        valid=False,
                        error=f"Invalid key (401)"
                    )
                
                # 其他错误（限流、服务器错误等）不标记为无效
                return UsageCheckResponse(
                    key=key,
                    valid=True,
                    error=f"API error: subscription={sub_response.status_code}, usage={usage_response.status_code}"
                )
                
        except httpx.TimeoutException:
            return UsageCheckResponse(
                key=key,
                valid=True,
                error="Timeout"
            )
        except Exception as e:
            return UsageCheckResponse(
                key=key,
                valid=True,
                error=str(e)
            )
    
    async def sync_key_usage(self, key_record: APIKeyRecord) -> str:
        """同步单个 Key 的余额到数据库，返回 'synced' / 'invalid' / 'failed'"""
        result = await self.check_single_key(key_record.key)
        
        if result.remaining is not None and result.valid:
            await db.sync_key_balance(
                key_id=key_record.id,
                balance=result.remaining
            )
            return "synced"
        elif not result.valid:
            from models import KeyStatus
            await db.update_key_status(key_record.id, KeyStatus.INVALID)
            return "invalid"
        
        return "failed"
    
    async def sync_all_keys(self, batch_size: int = 50) -> dict:
        """同步所有 Key 的余额（大批量并发）"""
        keys = await db.get_all_keys()
        results = {
            "total": len(keys),
            "synced": 0,
            "failed": 0,
            "invalid": 0
        }
        
        for i in range(0, len(keys), batch_size):
            batch = keys[i:i + batch_size]
            tasks = [self.sync_key_usage(key) for key in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in batch_results:
                if result is True:
                    results["synced"] += 1
                elif result is False:
                    results["invalid"] += 1
                else:
                    results["failed"] += 1
            
            if i + batch_size < len(keys):
                await asyncio.sleep(0.2)
        
        return results


usage_checker = UsageChecker()
