"""Branches router."""
from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, HTTPException, status

from dependencies import CurrentUser, DbSession, OrgAdminOrAbove
from models.user import UserRole
from repositories.branch import BranchRepository
from repositories.organization import MembershipRepository
from schemas.branch import BranchCreate, BranchOut, BranchUpdate
from schemas.common import PaginatedResponse

router = APIRouter(prefix="/branches", tags=["Branches"])


async def _get_org_id(current_user, db) -> uuid.UUID:
    if current_user.role == UserRole.SUPER_ADMIN:
        return None
    mem_repo = MembershipRepository(db)
    org_id = await mem_repo.get_user_org_id(current_user.id)
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No organization associated with this user",
        )
    return org_id


@router.get("", response_model=PaginatedResponse[BranchOut])
async def list_branches(
    db: DbSession,
    current_user: CurrentUser,
    page: int = 1,
    page_size: int = 20,
    active_only: bool = False,
):
    repo = BranchRepository(db)
    org_id = await _get_org_id(current_user, db)
    if org_id is None:
        # Super admin — list all (simplified: return empty or require org_id param)
        return PaginatedResponse(items=[], total=0, page=page, page_size=page_size, pages=0)

    rows, total = await repo.list_by_org(
        org_id, active_only=active_only, offset=(page - 1) * page_size, limit=page_size
    )
    return PaginatedResponse(
        items=[BranchOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("", response_model=BranchOut, status_code=201)
async def create_branch(
    data: BranchCreate,
    db: DbSession,
    current_user: OrgAdminOrAbove,
):
    org_id = await _get_org_id(current_user, db)
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="org_id required for super admin")

    from models.branch import PharmacyBranch, StorageConditionStatus
    branch = PharmacyBranch(
        id=uuid.uuid4(),
        organization_id=org_id,
        name=data.name,
        name_ar=data.name_ar,
        branch_code=data.branch_code,
        address=data.address,
        city=data.city,
        region=data.region,
        phone=data.phone,
        manager_name=data.manager_name,
        cold_chain_available=data.cold_chain_available,
        narcotics_license=data.narcotics_license,
        storage_condition_status=StorageConditionStatus.UNKNOWN,
    )
    db.add(branch)
    await db.flush()
    return BranchOut.model_validate(branch)


@router.get("/{branch_id}", response_model=BranchOut)
async def get_branch(branch_id: uuid.UUID, db: DbSession, current_user: CurrentUser):
    repo = BranchRepository(db)
    org_id = await _get_org_id(current_user, db)
    if org_id:
        branch = await repo.get_by_org(branch_id, org_id)
    else:
        branch = await repo.get(branch_id)
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    return BranchOut.model_validate(branch)


@router.patch("/{branch_id}", response_model=BranchOut)
async def update_branch(
    branch_id: uuid.UUID,
    data: BranchUpdate,
    db: DbSession,
    current_user: OrgAdminOrAbove,
):
    repo = BranchRepository(db)
    org_id = await _get_org_id(current_user, db)
    branch = await repo.get_by_org(branch_id, org_id)
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")

    for k, v in data.model_dump(exclude_unset=True).items():
        if hasattr(branch, k):
            setattr(branch, k, v)
    await db.flush()
    return BranchOut.model_validate(branch)


@router.delete("/{branch_id}", response_model=None, status_code=204)
async def delete_branch(
    branch_id: uuid.UUID,
    db: DbSession,
    current_user: OrgAdminOrAbove,
):
    repo = BranchRepository(db)
    org_id = await _get_org_id(current_user, db)
    branch = await repo.get_by_org(branch_id, org_id)
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    await repo.soft_delete(branch)
