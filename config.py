from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # 服务配置
    host: str = "0.0.0.0"
    port: int = 8000
    
    # 管理员密钥（用于访问 /admin 接口和作为统一的 API Key）
    admin_key: str = "sk-api-exchange-admin"
    
    # 上游 API 配置
    upstream_base_url: str = "https://api2.qiandao.mom/v1"
    
    # 用量查询配置
    usage_check_url: str = "https://key-check.qiandao.mom"
    
    # 数据库配置
    database_path: str = "keys.db"
    
    # 请求超时（秒）
    request_timeout: float = 120.0
    
    # 是否启用自动用量同步
    auto_sync_usage: bool = True
    
    # 用量同步间隔（秒）
    sync_interval: int = 300
    
    class Config:
        env_file = ".env"
        env_prefix = "API_EXCHANGE_"


@lru_cache
def get_settings() -> Settings:
    return Settings()
