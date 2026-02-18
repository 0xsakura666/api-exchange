import aiosqlite
import fnmatch
from typing import List, Optional
from datetime import datetime
from contextlib import asynccontextmanager

from models import APIKeyRecord, KeyStatus, APIKeyStats, ModelPricing, AccessToken
from config import get_settings


class Database:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or get_settings().database_path
        self._connection: Optional[aiosqlite.Connection] = None
    
    async def connect(self):
        """建立数据库连接"""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._init_tables()
    
    async def disconnect(self):
        """关闭数据库连接"""
        if self._connection:
            await self._connection.close()
            self._connection = None
    
    @asynccontextmanager
    async def get_connection(self):
        """获取数据库连接的上下文管理器"""
        if not self._connection:
            await self.connect()
        yield self._connection
    
    async def _init_tables(self):
        """初始化数据库表"""
        async with self.get_connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    balance REAL DEFAULT 0.24,
                    initial_balance REAL DEFAULT 0.24,
                    used_amount REAL DEFAULT 0,
                    request_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active',
                    last_used TIMESTAMP,
                    last_synced TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status ON api_keys(status)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_balance ON api_keys(balance)
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS model_pricing (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_pattern TEXT UNIQUE NOT NULL,
                    price_per_request REAL DEFAULT 0.08,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor = await conn.execute("SELECT COUNT(*) FROM model_pricing")
            count = (await cursor.fetchone())[0]
            if count == 0:
                default_pricing = [
                    ("gemini-3-pro-*", 0.08, "Gemini 3 Pro 系列"),
                    ("gemini-3-flash-*", 0.05, "Gemini 3 Flash 系列"),
                    ("gemini-2.5-pro-*", 0.07, "Gemini 2.5 Pro 系列"),
                    ("gemini-2.5-flash-*", 0.04, "Gemini 2.5 Flash 系列"),
                    ("claude-opus-*", 0.12, "Claude Opus 系列"),
                    ("claude-sonnet-*", 0.08, "Claude Sonnet 系列"),
                    ("GPT-5*", 0.10, "GPT-5 系列"),
                    ("DeepSeek-R1*", 0.06, "DeepSeek R1 推理模型"),
                    ("DeepSeek-V*", 0.05, "DeepSeek V 系列"),
                    ("*", 0.08, "默认价格（其他模型）"),
                ]
                await conn.executemany(
                    "INSERT INTO model_pricing (model_pattern, price_per_request, description) VALUES (?, ?, ?)",
                    default_pricing
                )
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS access_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    token TEXT UNIQUE NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    request_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP
                )
            """)
            
            await conn.commit()
    
    async def add_key(self, key: str, balance: float = 0.24) -> Optional[APIKeyRecord]:
        """添加新的 API Key"""
        async with self.get_connection() as conn:
            try:
                cursor = await conn.execute(
                    """
                    INSERT INTO api_keys (key, balance, initial_balance)
                    VALUES (?, ?, ?)
                    """,
                    (key, balance, balance)
                )
                await conn.commit()
                return await self.get_key_by_id(cursor.lastrowid)
            except aiosqlite.IntegrityError:
                return None
    
    async def add_keys_batch(self, keys: List[tuple]) -> int:
        """批量添加 API Key，返回成功添加的数量"""
        async with self.get_connection() as conn:
            added = 0
            for key, balance in keys:
                try:
                    await conn.execute(
                        """
                        INSERT OR IGNORE INTO api_keys (key, balance, initial_balance)
                        VALUES (?, ?, ?)
                        """,
                        (key, balance, balance)
                    )
                    added += conn.total_changes
                except Exception:
                    pass
            await conn.commit()
            return added
    
    async def get_key_by_id(self, key_id: int) -> Optional[APIKeyRecord]:
        """根据 ID 获取 Key"""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM api_keys WHERE id = ?",
                (key_id,)
            )
            row = await cursor.fetchone()
            return self._row_to_record(row) if row else None
    
    async def get_key_by_value(self, key: str) -> Optional[APIKeyRecord]:
        """根据 Key 值获取记录"""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM api_keys WHERE key = ?",
                (key,)
            )
            row = await cursor.fetchone()
            return self._row_to_record(row) if row else None
    
    async def get_available_key(self, min_balance: float = 0.01) -> Optional[APIKeyRecord]:
        """获取一个可用的 Key（状态为 active 且余额足够）"""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM api_keys 
                WHERE status = 'active' AND balance >= ?
                ORDER BY last_used ASC NULLS FIRST, id ASC
                LIMIT 1
                """,
                (min_balance,)
            )
            row = await cursor.fetchone()
            return self._row_to_record(row) if row else None
    
    async def get_all_keys(self, status: Optional[str] = None) -> List[APIKeyRecord]:
        """获取所有 Key"""
        async with self.get_connection() as conn:
            if status:
                cursor = await conn.execute(
                    "SELECT * FROM api_keys WHERE status = ? ORDER BY created_at DESC",
                    (status,)
                )
            else:
                cursor = await conn.execute(
                    "SELECT * FROM api_keys ORDER BY created_at DESC"
                )
            rows = await cursor.fetchall()
            return [self._row_to_record(row) for row in rows]
    
    async def deduct_balance(self, key_id: int, amount: float):
        """扣除余额"""
        async with self.get_connection() as conn:
            await conn.execute(
                """
                UPDATE api_keys 
                SET balance = balance - ?,
                    used_amount = used_amount + ?,
                    request_count = request_count + 1,
                    last_used = ?,
                    status = CASE WHEN balance - ? < 0.01 THEN 'exhausted' ELSE status END
                WHERE id = ?
                """,
                (amount, amount, datetime.now(), amount, key_id)
            )
            await conn.commit()
    
    async def update_key_status(self, key_id: int, status: KeyStatus):
        """更新 Key 状态"""
        async with self.get_connection() as conn:
            await conn.execute(
                "UPDATE api_keys SET status = ? WHERE id = ?",
                (status.value, key_id)
            )
            await conn.commit()
    
    async def sync_key_balance(self, key_id: int, balance: float):
        """同步远程查询的余额"""
        async with self.get_connection() as conn:
            status = KeyStatus.ACTIVE.value if balance >= 0.01 else KeyStatus.EXHAUSTED.value
            await conn.execute(
                """
                UPDATE api_keys 
                SET balance = ?, last_synced = ?, status = ?
                WHERE id = ?
                """,
                (balance, datetime.now(), status, key_id)
            )
            await conn.commit()
    
    async def get_stats(self) -> APIKeyStats:
        """获取统计信息"""
        async with self.get_connection() as conn:
            cursor = await conn.execute("""
                SELECT 
                    COUNT(*) as total_keys,
                    SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_keys,
                    SUM(CASE WHEN status = 'exhausted' THEN 1 ELSE 0 END) as exhausted_keys,
                    SUM(CASE WHEN status = 'invalid' THEN 1 ELSE 0 END) as invalid_keys,
                    SUM(balance) as total_balance,
                    SUM(used_amount) as total_used,
                    SUM(request_count) as total_requests
                FROM api_keys
            """)
            row = await cursor.fetchone()
            return APIKeyStats(
                total_keys=row["total_keys"] or 0,
                active_keys=row["active_keys"] or 0,
                exhausted_keys=row["exhausted_keys"] or 0,
                invalid_keys=row["invalid_keys"] or 0,
                total_balance=round(row["total_balance"] or 0, 4),
                total_used=round(row["total_used"] or 0, 4),
                total_requests=row["total_requests"] or 0
            )
    
    async def delete_key(self, key_id: int) -> bool:
        """删除 Key"""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM api_keys WHERE id = ?",
                (key_id,)
            )
            await conn.commit()
            return cursor.rowcount > 0
    
    async def get_model_price(self, model: str) -> float:
        """获取模型价格（支持通配符匹配）"""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT model_pattern, price_per_request FROM model_pricing ORDER BY id"
            )
            rows = await cursor.fetchall()
            
            for row in rows:
                pattern = row["model_pattern"]
                if fnmatch.fnmatch(model.lower(), pattern.lower()):
                    return row["price_per_request"]
            
            return 0.08
    
    async def get_all_pricing(self) -> List[ModelPricing]:
        """获取所有模型定价"""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM model_pricing ORDER BY id"
            )
            rows = await cursor.fetchall()
            return [
                ModelPricing(
                    id=row["id"],
                    model_pattern=row["model_pattern"],
                    price_per_request=row["price_per_request"],
                    description=row["description"],
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now()
                )
                for row in rows
            ]
    
    async def add_pricing(self, model_pattern: str, price: float, description: str = None) -> Optional[ModelPricing]:
        """添加模型定价"""
        async with self.get_connection() as conn:
            try:
                cursor = await conn.execute(
                    "INSERT INTO model_pricing (model_pattern, price_per_request, description) VALUES (?, ?, ?)",
                    (model_pattern, price, description)
                )
                await conn.commit()
                return ModelPricing(
                    id=cursor.lastrowid,
                    model_pattern=model_pattern,
                    price_per_request=price,
                    description=description
                )
            except aiosqlite.IntegrityError:
                return None
    
    async def update_pricing(self, pricing_id: int, price: float, description: str = None) -> bool:
        """更新模型定价"""
        async with self.get_connection() as conn:
            await conn.execute(
                "UPDATE model_pricing SET price_per_request = ?, description = ? WHERE id = ?",
                (price, description, pricing_id)
            )
            await conn.commit()
            return True
    
    async def delete_pricing(self, pricing_id: int) -> bool:
        """删除模型定价"""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM model_pricing WHERE id = ?",
                (pricing_id,)
            )
            await conn.commit()
            return cursor.rowcount > 0
    
    async def create_access_token(self, name: str, token: str) -> AccessToken:
        """创建访问令牌"""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "INSERT INTO access_tokens (name, token) VALUES (?, ?)",
                (name, token)
            )
            await conn.commit()
            return AccessToken(
                id=cursor.lastrowid,
                name=name,
                token=token,
                enabled=True,
                request_count=0
            )
    
    async def get_all_access_tokens(self) -> List[AccessToken]:
        """获取所有访问令牌"""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM access_tokens ORDER BY created_at DESC"
            )
            rows = await cursor.fetchall()
            return [
                AccessToken(
                    id=row["id"],
                    name=row["name"],
                    token=row["token"],
                    enabled=bool(row["enabled"]),
                    request_count=row["request_count"],
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(),
                    last_used=datetime.fromisoformat(row["last_used"]) if row["last_used"] else None
                )
                for row in rows
            ]
    
    async def verify_access_token(self, token: str) -> Optional[AccessToken]:
        """验证访问令牌是否有效"""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM access_tokens WHERE token = ? AND enabled = 1",
                (token,)
            )
            row = await cursor.fetchone()
            if row:
                await conn.execute(
                    "UPDATE access_tokens SET request_count = request_count + 1, last_used = ? WHERE id = ?",
                    (datetime.now(), row["id"])
                )
                await conn.commit()
                return AccessToken(
                    id=row["id"],
                    name=row["name"],
                    token=row["token"],
                    enabled=bool(row["enabled"]),
                    request_count=row["request_count"],
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(),
                    last_used=datetime.fromisoformat(row["last_used"]) if row["last_used"] else None
                )
            return None
    
    async def toggle_access_token(self, token_id: int, enabled: bool) -> bool:
        """启用/禁用访问令牌"""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "UPDATE access_tokens SET enabled = ? WHERE id = ?",
                (1 if enabled else 0, token_id)
            )
            await conn.commit()
            return cursor.rowcount > 0
    
    async def delete_access_token(self, token_id: int) -> bool:
        """删除访问令牌"""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM access_tokens WHERE id = ?",
                (token_id,)
            )
            await conn.commit()
            return cursor.rowcount > 0
    
    def _row_to_record(self, row) -> APIKeyRecord:
        """将数据库行转换为 APIKeyRecord"""
        return APIKeyRecord(
            id=row["id"],
            key=row["key"],
            balance=row["balance"],
            initial_balance=row["initial_balance"],
            used_amount=row["used_amount"],
            request_count=row["request_count"],
            status=KeyStatus(row["status"]),
            last_used=datetime.fromisoformat(row["last_used"]) if row["last_used"] else None,
            last_synced=datetime.fromisoformat(row["last_synced"]) if row["last_synced"] else None,
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now()
        )


db = Database()
