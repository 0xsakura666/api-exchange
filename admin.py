from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List
import csv
import io
import secrets

from models import APIKeyCreate, APIKeyImport, APIKeyRecord, APIKeyStats, ModelPricing, ModelPricingCreate, AccessToken, AccessTokenCreate
from config import get_settings
from key_manager import key_manager
from database import db

router = APIRouter(prefix="/admin", tags=["Admin"])
security = HTTPBearer()


async def verify_admin_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """验证管理员密钥"""
    settings = get_settings()
    if credentials.credentials != settings.admin_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid admin key"
        )
    return credentials.credentials


@router.get("/keys")
async def list_keys(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    _: str = Depends(verify_admin_key)
):
    """获取所有 API Keys（分页）"""
    all_keys = await key_manager.get_all_keys(status)
    total = len(all_keys)
    total_pages = (total + page_size - 1) // page_size
    
    start = (page - 1) * page_size
    end = start + page_size
    keys = all_keys[start:end]
    
    return {
        "keys": keys,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.post("/keys", response_model=dict)
async def add_key(
    key_data: APIKeyCreate,
    _: str = Depends(verify_admin_key)
):
    """添加单个 API Key"""
    record = await db.add_key(key_data.key, key_data.balance)
    if record:
        return {"success": True, "key": record}
    return {"success": False, "message": "Key already exists"}


@router.post("/keys/import", response_model=dict)
async def import_keys(
    data: APIKeyImport,
    _: str = Depends(verify_admin_key)
):
    """批量导入 API Keys (JSON)"""
    keys = [(k.key, k.balance) for k in data.keys]
    result = await key_manager.import_keys(keys)
    return result


@router.post("/keys/import/csv", response_model=dict)
async def import_keys_csv(
    file: UploadFile = File(...),
    _: str = Depends(verify_admin_key)
):
    """
    从 CSV 文件导入 API Keys
    CSV 格式: key,balance (balance 可选，默认为 0.24)
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    content = await file.read()
    text = content.decode("utf-8")
    
    keys = []
    reader = csv.reader(io.StringIO(text))
    
    for row in reader:
        if not row or row[0].startswith("#"):
            continue
        
        # 去除所有空格
        key = row[0].strip().replace(" ", "").replace("\t", "")
        if not key or not key.startswith("sk-"):
            continue
            
        balance = 0.24
        if len(row) > 1:
            try:
                balance = float(row[1].strip())
            except ValueError:
                pass
        
        keys.append((key, balance))
    
    result = await key_manager.import_keys(keys)
    return result


@router.post("/keys/import/text", response_model=dict)
async def import_keys_text(
    file: UploadFile = File(...),
    default_balance: float = 0.24,
    _: str = Depends(verify_admin_key)
):
    """
    从纯文本文件导入 API Keys (每行一个 key)
    """
    content = await file.read()
    text = content.decode("utf-8")
    
    keys = []
    for line in text.strip().split("\n"):
        # 去除所有空格
        key = line.strip().replace(" ", "").replace("\t", "")
        if key and key.startswith("sk-") and not key.startswith("#"):
            keys.append((key, default_balance))
    
    result = await key_manager.import_keys(keys)
    return result


@router.delete("/keys/{key_id}")
async def delete_key(
    key_id: int,
    _: str = Depends(verify_admin_key)
):
    """删除指定的 API Key"""
    success = await db.delete_key(key_id)
    if success:
        return {"success": True}
    raise HTTPException(status_code=404, detail="Key not found")


@router.delete("/keys/invalid/batch")
async def delete_invalid_keys(_: str = Depends(verify_admin_key)):
    """批量删除无效的 Keys（包含空格或不以 sk- 开头的）"""
    all_keys = await db.get_all_keys()
    deleted = 0
    for key in all_keys:
        # 检查是否包含空格或不以 sk- 开头
        if ' ' in key.key or '\t' in key.key or not key.key.startswith('sk-'):
            await db.delete_key(key.id)
            deleted += 1
    return {"deleted": deleted}


@router.get("/stats", response_model=APIKeyStats)
async def get_stats(_: str = Depends(verify_admin_key)):
    """获取统计信息"""
    return await key_manager.get_stats()


@router.get("/pricing", response_model=List[ModelPricing])
async def list_pricing(_: str = Depends(verify_admin_key)):
    """获取所有模型定价配置"""
    return await db.get_all_pricing()


@router.post("/pricing", response_model=dict)
async def add_pricing(
    data: ModelPricingCreate,
    _: str = Depends(verify_admin_key)
):
    """添加模型定价"""
    result = await db.add_pricing(data.model_pattern, data.price_per_request, data.description)
    if result:
        return {"success": True, "pricing": result}
    return {"success": False, "message": "Pattern already exists"}


@router.put("/pricing/{pricing_id}")
async def update_pricing(
    pricing_id: int,
    data: ModelPricingCreate,
    _: str = Depends(verify_admin_key)
):
    """更新模型定价"""
    success = await db.update_pricing(pricing_id, data.price_per_request, data.description)
    if success:
        return {"success": True}
    raise HTTPException(status_code=404, detail="Pricing not found")


@router.delete("/pricing/{pricing_id}")
async def delete_pricing(
    pricing_id: int,
    _: str = Depends(verify_admin_key)
):
    """删除模型定价"""
    success = await db.delete_pricing(pricing_id)
    if success:
        return {"success": True}
    raise HTTPException(status_code=404, detail="Pricing not found")


@router.get("/pricing/check")
async def check_model_price(
    model: str,
    _: str = Depends(verify_admin_key)
):
    """查询指定模型的价格"""
    price = await db.get_model_price(model)
    return {"model": model, "price": price}




SUPPORTED_MODELS = [
    {"category": "Gemini 3", "models": [
        "gemini-3-pro-preview-y",
        "gemini-3-pro-preview-u",
        "gemini-3-pro-preview-v",
        "gemini-3-pro-preview-h",
        "gemini-3-pro-preview-S",
        "gemini-3-pro-preview-cc",
        "gemini-3-pro-preview-thinking-v",
        "gemini-3-pro-image-preview-s",
        "gemini-3-pro-image-preview-gg",
        "gemini-3-flash-preview-S",
    ]},
    {"category": "Gemini 2.5", "models": [
        "gemini-2.5-pro-preview-p",
        "gemini-2.5-flash-image-preview-s",
    ]},
    {"category": "Claude Opus", "models": [
        "claude-opus-4-6-k",
        "claude-opus-4-6-thinking-k",
        "claude-opus-4-5-20251101-k",
        "claude-opus-4-5-20251101-thinking-k",
    ]},
    {"category": "Claude Sonnet", "models": [
        "claude-sonnet-4-6-20260217-k",
        "claude-sonnet-4-6-20260217-thinking-k",
        "claude-sonnet-4-5-20250929-k",
        "claude-sonnet-4-5-20250929-thinking-k",
    ]},
    {"category": "GPT", "models": [
        "GPT-5.1-a",
        "GPT-5.2-a",
    ]},
    {"category": "DeepSeek", "models": [
        "DeepSeek-R1-a",
        "DeepSeek-V1-a",
        "DeepSeek-V3.1-a",
        "DeepSeek-V3.2-a",
    ]},
]


@router.get("/models")
async def list_upstream_models(_: str = Depends(verify_admin_key)):
    """获取支持的模型列表（固定列表）"""
    categories = []
    total = 0
    
    for cat in SUPPORTED_MODELS:
        models = []
        for model_id in cat["models"]:
            price = await db.get_model_price(model_id)
            models.append({
                "id": model_id,
                "price": price
            })
            total += 1
        categories.append({
            "name": cat["category"],
            "models": models
        })
    
    return {
        "categories": categories,
        "total": total
    }


@router.get("/tokens", response_model=List[AccessToken])
async def list_tokens(_: str = Depends(verify_admin_key)):
    """获取所有对外访问令牌"""
    return await db.get_all_access_tokens()


@router.post("/tokens", response_model=AccessToken)
async def create_token(
    data: AccessTokenCreate,
    _: str = Depends(verify_admin_key)
):
    """创建新的对外访问令牌"""
    token = "sk-ex-" + secrets.token_urlsafe(32)
    return await db.create_access_token(data.name, token)


@router.put("/tokens/{token_id}/toggle")
async def toggle_token(
    token_id: int,
    enabled: bool,
    _: str = Depends(verify_admin_key)
):
    """启用/禁用访问令牌"""
    success = await db.toggle_access_token(token_id, enabled)
    if success:
        return {"success": True}
    raise HTTPException(status_code=404, detail="Token not found")


@router.delete("/tokens/{token_id}")
async def delete_token(
    token_id: int,
    _: str = Depends(verify_admin_key)
):
    """删除访问令牌"""
    success = await db.delete_access_token(token_id)
    if success:
        return {"success": True}
    raise HTTPException(status_code=404, detail="Token not found")
