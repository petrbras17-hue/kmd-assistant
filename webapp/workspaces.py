"""
Роутер для управления рабочими пространствами (Workspaces / Организации).

Предоставляет CRUD-операции для воркспейсов, управление участниками
и хелпер для изоляции данных по воркспейсу.
"""

import re
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from webapp.database import get_db
from webapp.models import Project, User, Workspace, WorkspaceMember

from webapp.auth import get_current_user


# ---------------------------------------------------------------------------
# Pydantic-схемы
# ---------------------------------------------------------------------------

class WorkspaceCreate(BaseModel):
    """Схема создания воркспейса."""
    name: str = Field(..., min_length=1, max_length=512, description="Название организации")
    slug: Optional[str] = Field(
        None, max_length=128,
        description="URL-slug (генерируется автоматически, если не указан)",
    )
    logo_url: Optional[str] = Field(None, max_length=2048)
    plan: str = Field("free", max_length=64)
    max_members: int = Field(5, ge=1, le=1000)


class WorkspaceUpdate(BaseModel):
    """Схема обновления воркспейса (все поля необязательны)."""
    name: Optional[str] = Field(None, min_length=1, max_length=512)
    slug: Optional[str] = Field(None, max_length=128)
    logo_url: Optional[str] = Field(None, max_length=2048)
    plan: Optional[str] = Field(None, max_length=64)
    max_members: Optional[int] = Field(None, ge=1, le=1000)


class MemberOut(BaseModel):
    """Участник воркспейса (ответ)."""
    id: int
    user_id: int
    username: str
    email: Optional[str] = None
    role: str
    joined_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceOut(BaseModel):
    """Воркспейс (ответ)."""
    id: int
    name: str
    slug: str
    logo_url: Optional[str] = None
    plan: str
    max_members: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    member_count: int = 0

    model_config = {"from_attributes": True}


class WorkspaceDetailOut(WorkspaceOut):
    """Воркспейс с участниками (подробный ответ)."""
    members: List[MemberOut] = []


class InviteRequest(BaseModel):
    """Запрос на приглашение пользователя."""
    email: str = Field(..., description="Email приглашаемого пользователя")
    role: str = Field("engineer", max_length=32, description="Роль: admin, engineer, viewer")


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    """Генерирует URL-slug из произвольного текста."""
    # Транслитерация кириллицы не выполняется — slug должен быть латиницей
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug[:128] or "workspace"


async def _get_membership(
    db: AsyncSession, workspace_id: int, user_id: int
) -> Optional[WorkspaceMember]:
    """Получить запись участия пользователя в воркспейсе."""
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def _require_admin(
    db: AsyncSession, workspace_id: int, user_id: int
) -> WorkspaceMember:
    """Проверить, что пользователь — администратор воркспейса."""
    member = await _get_membership(db, workspace_id, user_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Вы не являетесь участником этого воркспейса.",
        )
    if member.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администратор может выполнять это действие.",
        )
    return member


def _member_to_out(member: WorkspaceMember) -> MemberOut:
    """Конвертировать ORM-объект WorkspaceMember в Pydantic-схему."""
    return MemberOut(
        id=member.id,
        user_id=member.user_id,
        username=member.user.username,
        email=member.user.email,
        role=member.role,
        joined_at=member.joined_at,
    )


# ---------------------------------------------------------------------------
# Зависимость для изоляции данных по воркспейсу
# ---------------------------------------------------------------------------

async def get_workspace_filter(
    workspace_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Optional[int]:
    """Зависимость FastAPI, обеспечивающая изоляцию данных по воркспейсу.

    Если workspace_id передан — проверяет, что текущий пользователь
    является участником воркспейса, и возвращает workspace_id для
    использования в фильтрах запросов (например, Project.workspace_id == ws_id).

    Если workspace_id не передан — возвращает None (без фильтрации).
    """
    if workspace_id is None:
        return None

    membership = await _get_membership(db, workspace_id, current_user.id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="У вас нет доступа к этому воркспейсу.",
        )
    return workspace_id


# ---------------------------------------------------------------------------
# Роутер
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    body: WorkspaceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать новое рабочее пространство.

    Создатель автоматически добавляется как admin.
    """
    slug = body.slug or _slugify(body.name)

    # Проверка уникальности slug
    existing = await db.execute(select(Workspace).where(Workspace.slug == slug))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Воркспейс со slug '{slug}' уже существует.",
        )

    workspace = Workspace(
        name=body.name,
        slug=slug,
        logo_url=body.logo_url,
        plan=body.plan,
        max_members=body.max_members,
    )
    db.add(workspace)
    await db.flush()

    # Автоматически добавляем создателя как admin
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=current_user.id,
        role="admin",
    )
    db.add(member)
    await db.flush()

    return WorkspaceOut(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        logo_url=workspace.logo_url,
        plan=workspace.plan,
        max_members=workspace.max_members,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
        member_count=1,
    )


@router.get("", response_model=List[WorkspaceOut])
async def list_workspaces(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить список воркспейсов текущего пользователя."""
    result = await db.execute(
        select(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == current_user.id)
        .options(selectinload(Workspace.members))
    )
    workspaces = result.scalars().unique().all()

    return [
        WorkspaceOut(
            id=ws.id,
            name=ws.name,
            slug=ws.slug,
            logo_url=ws.logo_url,
            plan=ws.plan,
            max_members=ws.max_members,
            created_at=ws.created_at,
            updated_at=ws.updated_at,
            member_count=len(ws.members),
        )
        for ws in workspaces
    ]


@router.get("/{workspace_id}", response_model=WorkspaceDetailOut)
async def get_workspace(
    workspace_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить подробную информацию о воркспейсе (включая участников)."""
    result = await db.execute(
        select(Workspace)
        .where(Workspace.id == workspace_id)
        .options(
            selectinload(Workspace.members).selectinload(WorkspaceMember.user)
        )
    )
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Воркспейс не найден.",
        )

    # Проверяем, что пользователь — участник
    membership = await _get_membership(db, workspace_id, current_user.id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="У вас нет доступа к этому воркспейсу.",
        )

    return WorkspaceDetailOut(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        logo_url=workspace.logo_url,
        plan=workspace.plan,
        max_members=workspace.max_members,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
        member_count=len(workspace.members),
        members=[_member_to_out(m) for m in workspace.members],
    )


@router.put("/{workspace_id}", response_model=WorkspaceOut)
async def update_workspace(
    workspace_id: int,
    body: WorkspaceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновить воркспейс (только для администратора)."""
    await _require_admin(db, workspace_id, current_user.id)

    result = await db.execute(
        select(Workspace)
        .where(Workspace.id == workspace_id)
        .options(selectinload(Workspace.members))
    )
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Воркспейс не найден.",
        )

    update_data = body.model_dump(exclude_unset=True)

    # Проверка уникальности нового slug
    if "slug" in update_data and update_data["slug"] != workspace.slug:
        existing = await db.execute(
            select(Workspace).where(Workspace.slug == update_data["slug"])
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Воркспейс со slug '{update_data['slug']}' уже существует.",
            )

    for field, value in update_data.items():
        setattr(workspace, field, value)

    await db.flush()

    return WorkspaceOut(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        logo_url=workspace.logo_url,
        plan=workspace.plan,
        max_members=workspace.max_members,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
        member_count=len(workspace.members),
    )


@router.post("/{workspace_id}/invite", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
async def invite_member(
    workspace_id: int,
    body: InviteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Пригласить пользователя в воркспейс по email (только для администратора)."""
    await _require_admin(db, workspace_id, current_user.id)

    # Проверяем существование воркспейса и лимит участников
    ws_result = await db.execute(
        select(Workspace)
        .where(Workspace.id == workspace_id)
        .options(selectinload(Workspace.members))
    )
    workspace = ws_result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Воркспейс не найден.",
        )

    if len(workspace.members) >= workspace.max_members:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Достигнут лимит участников ({workspace.max_members}). "
                   f"Обновите тарифный план для увеличения лимита.",
        )

    # Валидация роли
    allowed_roles = {"admin", "engineer", "viewer"}
    if body.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Недопустимая роль '{body.role}'. Допустимые: {', '.join(sorted(allowed_roles))}.",
        )

    # Найти пользователя по email
    user_result = await db.execute(
        select(User).where(User.email == body.email)
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с email '{body.email}' не найден.",
        )

    # Проверяем, не является ли пользователь уже участником
    existing = await _get_membership(db, workspace_id, user.id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь уже является участником этого воркспейса.",
        )

    member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=user.id,
        role=body.role,
    )
    db.add(member)
    await db.flush()

    return MemberOut(
        id=member.id,
        user_id=user.id,
        username=user.username,
        email=user.email,
        role=member.role,
        joined_at=member.joined_at,
    )


@router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    workspace_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Удалить участника из воркспейса (только для администратора).

    Администратор не может удалить сам себя, если он единственный admin.
    """
    await _require_admin(db, workspace_id, current_user.id)

    member = await _get_membership(db, workspace_id, user_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Участник не найден в этом воркспейсе.",
        )

    # Защита от удаления последнего администратора
    if member.role == "admin":
        admin_count_result = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == "admin",
            )
        )
        admins = admin_count_result.scalars().all()
        if len(admins) <= 1:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Невозможно удалить единственного администратора воркспейса.",
            )

    await db.delete(member)
    await db.flush()


@router.get("/{workspace_id}/members", response_model=List[MemberOut])
async def list_members(
    workspace_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить список участников воркспейса."""
    # Проверяем, что текущий пользователь — участник
    membership = await _get_membership(db, workspace_id, current_user.id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="У вас нет доступа к этому воркспейсу.",
        )

    result = await db.execute(
        select(WorkspaceMember)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .options(selectinload(WorkspaceMember.user))
    )
    members = result.scalars().all()

    return [_member_to_out(m) for m in members]
