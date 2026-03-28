import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.llm_connection import LLMConnection
from app.models.user import User
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Provider → available models
PROVIDER_MODELS = {
    "openai": [
        {"id": "gpt-4o-mini", "label": "GPT-4o Mini — дешёвая"},
        {"id": "gpt-4o", "label": "GPT-4o"},
        {"id": "gpt-4.1-mini", "label": "GPT-4.1 Mini — дешёвая"},
        {"id": "gpt-4.1-nano", "label": "GPT-4.1 Nano — самая дешёвая"},
        {"id": "whisper-1", "label": "Whisper-1 (только STT)"},
    ],
    "anthropic": [
        {"id": "claude-haiku-4-5-20251001", "label": "Claude Haiku 4.5 — дешёвая"},
        {"id": "claude-sonnet-4-20250514", "label": "Claude Sonnet 4"},
    ],
}

PURPOSES = {
    "chat": "Чат / ответы",
    "stt": "Распознавание голоса (STT)",
}


def mask_key(key: str) -> str:
    if not key or len(key) < 8:
        return ""
    return key[:6] + "..." + key[-4:]


async def _test_openai(api_key: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code == 200:
                return {"connected": True}
            if resp.status_code == 401:
                return {"connected": False, "error": "Неверный API-ключ"}
            return {"connected": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"connected": False, "error": str(e)}


async def _test_anthropic(api_key: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
            if resp.status_code in (200, 201):
                return {"connected": True}
            if resp.status_code == 401:
                return {"connected": False, "error": "Неверный API-ключ"}
            return {"connected": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"connected": False, "error": str(e)}


# --- Schemas ---

class ModelOption(BaseModel):
    id: str
    label: str


class ProviderInfo(BaseModel):
    id: str
    label: str
    models: list[ModelOption]


class LLMConnectionResponse(BaseModel):
    id: int
    name: str
    provider: str
    masked_key: str
    model: str
    purpose: str
    purpose_label: str
    is_default: bool
    connected: bool | None = None
    error: str | None = None
    created_at: str

    model_config = {"from_attributes": True}


class LLMConnectionCreate(BaseModel):
    name: str
    provider: str
    api_key: str
    model: str
    purpose: str
    is_default: bool = False


class LLMConnectionUpdate(BaseModel):
    name: str | None = None
    api_key: str | None = None
    model: str | None = None
    purpose: str | None = None
    is_default: bool | None = None


class SettingsOverview(BaseModel):
    connections: list[LLMConnectionResponse]
    providers: list[ProviderInfo]
    purposes: dict[str, str]


# --- Helpers ---

def _to_response(conn: LLMConnection, connected: bool | None = None, error: str | None = None) -> LLMConnectionResponse:
    return LLMConnectionResponse(
        id=conn.id,
        name=conn.name,
        provider=conn.provider,
        masked_key=mask_key(conn.api_key),
        model=conn.model,
        purpose=conn.purpose,
        purpose_label=PURPOSES.get(conn.purpose, conn.purpose),
        is_default=conn.is_default,
        connected=connected,
        error=error,
        created_at=conn.created_at.isoformat() if conn.created_at else "",
    )


# --- Endpoints ---

@router.get("", response_model=SettingsOverview)
async def get_settings(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(LLMConnection).order_by(LLMConnection.id))
    connections = [_to_response(c) for c in result.scalars().all()]

    providers = [
        ProviderInfo(id=pid, label=pid.capitalize(), models=[ModelOption(**m) for m in models])
        for pid, models in PROVIDER_MODELS.items()
    ]

    return SettingsOverview(connections=connections, providers=providers, purposes=PURPOSES)


@router.post("/connections", response_model=LLMConnectionResponse, status_code=201)
async def create_connection(
    body: LLMConnectionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.provider not in PROVIDER_MODELS:
        raise HTTPException(400, f"Неизвестный провайдер: {body.provider}")
    if body.purpose not in PURPOSES:
        raise HTTPException(400, f"Неизвестное назначение: {body.purpose}")

    # If is_default, unset other defaults for same purpose
    if body.is_default:
        result = await db.execute(
            select(LLMConnection).where(LLMConnection.purpose == body.purpose, LLMConnection.is_default == True)
        )
        for c in result.scalars().all():
            c.is_default = False

    conn = LLMConnection(
        name=body.name,
        provider=body.provider,
        api_key=body.api_key,
        model=body.model,
        purpose=body.purpose,
        is_default=body.is_default,
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    return _to_response(conn)


@router.put("/connections/{conn_id}", response_model=LLMConnectionResponse)
async def update_connection(
    conn_id: int,
    body: LLMConnectionUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(LLMConnection).where(LLMConnection.id == conn_id))
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(404, "Подключение не найдено")

    update_data = body.model_dump(exclude_unset=True)

    # If setting as default, unset other defaults for same purpose
    if update_data.get("is_default"):
        purpose = update_data.get("purpose", conn.purpose)
        others = await db.execute(
            select(LLMConnection).where(
                LLMConnection.purpose == purpose,
                LLMConnection.is_default == True,
                LLMConnection.id != conn_id,
            )
        )
        for c in others.scalars().all():
            c.is_default = False

    for field, value in update_data.items():
        setattr(conn, field, value)

    await db.commit()
    await db.refresh(conn)
    return _to_response(conn)


@router.delete("/connections/{conn_id}", status_code=204)
async def delete_connection(
    conn_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(LLMConnection).where(LLMConnection.id == conn_id))
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(404, "Подключение не найдено")
    await db.delete(conn)
    await db.commit()


@router.post("/connections/{conn_id}/test", response_model=LLMConnectionResponse)
async def test_connection(
    conn_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(LLMConnection).where(LLMConnection.id == conn_id))
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(404, "Подключение не найдено")

    if conn.provider == "openai":
        status = await _test_openai(conn.api_key)
    elif conn.provider == "anthropic":
        status = await _test_anthropic(conn.api_key)
    else:
        status = {"connected": False, "error": "Неизвестный провайдер"}

    return _to_response(conn, connected=status.get("connected"), error=status.get("error"))


@router.post("/test-all", response_model=list[LLMConnectionResponse])
async def test_all_connections(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(LLMConnection).order_by(LLMConnection.id))
    responses = []
    for conn in result.scalars().all():
        if conn.provider == "openai":
            status = await _test_openai(conn.api_key)
        elif conn.provider == "anthropic":
            status = await _test_anthropic(conn.api_key)
        else:
            status = {"connected": False, "error": "Неизвестный провайдер"}
        responses.append(_to_response(conn, connected=status.get("connected"), error=status.get("error")))
    return responses
