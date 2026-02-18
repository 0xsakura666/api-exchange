from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum


class KeyStatus(str, Enum):
    ACTIVE = "active"
    EXHAUSTED = "exhausted"
    INVALID = "invalid"


class APIKeyRecord(BaseModel):
    """API Key 数据库记录"""
    id: Optional[int] = None
    key: str
    balance: float = 0.24
    initial_balance: float = 0.24
    used_amount: float = 0.0
    request_count: int = 0
    status: KeyStatus = KeyStatus.ACTIVE
    last_used: Optional[datetime] = None
    last_synced: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        use_enum_values = True


class APIKeyCreate(BaseModel):
    """创建 API Key 的请求"""
    key: str
    balance: float = 0.24


class APIKeyImport(BaseModel):
    """批量导入 API Key"""
    keys: List[APIKeyCreate]


class APIKeyStats(BaseModel):
    """API Key 统计信息"""
    total_keys: int
    active_keys: int
    exhausted_keys: int
    invalid_keys: int
    total_balance: float
    total_used: float
    total_requests: int


class ModelPricing(BaseModel):
    """模型计费配置"""
    id: Optional[int] = None
    model_pattern: str
    price_per_request: float = 0.08
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


class ModelPricingCreate(BaseModel):
    """创建模型计费配置"""
    model_pattern: str
    price_per_request: float
    description: Optional[str] = None


class ChatMessage(BaseModel):
    """聊天消息"""
    role: str
    content: Any


class ChatCompletionRequest(BaseModel):
    """Chat Completion 请求"""
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    n: Optional[int] = None
    stream: Optional[bool] = False
    stop: Optional[Any] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    user: Optional[str] = None
    
    class Config:
        extra = "allow"


class UsageCheckResponse(BaseModel):
    """用量查询响应"""
    key: str
    remaining: Optional[float] = None
    used: Optional[float] = None
    total: Optional[float] = None
    valid: bool = True
    error: Optional[str] = None


class AccessToken(BaseModel):
    """对外访问令牌"""
    id: Optional[int] = None
    name: str
    token: str
    enabled: bool = True
    request_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    last_used: Optional[datetime] = None


class AccessTokenCreate(BaseModel):
    """创建访问令牌"""
    name: str
