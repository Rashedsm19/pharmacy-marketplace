"""Products and categories router."""
from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, HTTPException, status

from dependencies import CurrentUser, DbSession, SuperAdmin
from repositories.product import ProductCategoryRepository, ProductRepository
from schemas.common import PaginatedResponse
from schemas.product import (
    ProductCategoryCreate,
    ProductCategoryOut,
    ProductCategoryUpdate,
    ProductCreate,
    ProductOut,
    ProductUpdate,
)

router = APIRouter(prefix="/products", tags=["Products"])


# ── Categories ────────────────────────────────────────────────────────────────

@router.get("/categories", response_model=list[ProductCategoryOut])
async def list_categories(db: DbSession, current_user: CurrentUser):
    repo = ProductCategoryRepository(db)
    rows = await repo.list_all()
    return [ProductCategoryOut.model_validate(r) for r in rows]


@router.post("/categories", response_model=ProductCategoryOut, status_code=201)
async def create_category(
    data: ProductCategoryCreate,
    db: DbSession,
    current_user: SuperAdmin,
):
    repo = ProductCategoryRepository(db)
    existing = await repo.get_by_code(data.code)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category code already exists")

    from models.product import ProductCategory
    cat = ProductCategory(id=uuid.uuid4(), **data.model_dump())
    db.add(cat)
    await db.flush()
    return ProductCategoryOut.model_validate(cat)


@router.patch("/categories/{cat_id}", response_model=ProductCategoryOut)
async def update_category(
    cat_id: uuid.UUID,
    data: ProductCategoryUpdate,
    db: DbSession,
    current_user: SuperAdmin,
):
    repo = ProductCategoryRepository(db)
    cat = await repo.get(cat_id)
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    await db.flush()
    return ProductCategoryOut.model_validate(cat)


# ── Products ──────────────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedResponse[ProductOut])
async def list_products(
    db: DbSession,
    current_user: CurrentUser,
    search: str | None = None,
    category_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
):
    repo = ProductRepository(db)
    rows, total = await repo.list_active(
        search=search,
        category_id=category_id,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return PaginatedResponse(
        items=[ProductOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("", response_model=ProductOut, status_code=201)
async def create_product(
    data: ProductCreate,
    db: DbSession,
    current_user: SuperAdmin,
):
    repo = ProductRepository(db)
    existing = await repo.get_by_sku(data.sku)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SKU already exists")

    from models.product import Product
    product = Product(id=uuid.uuid4(), **data.model_dump())
    db.add(product)
    await db.flush()
    return ProductOut.model_validate(product)


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(product_id: uuid.UUID, db: DbSession, current_user: CurrentUser):
    repo = ProductRepository(db)
    product = await repo.get(product_id)
    if not product or product.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return ProductOut.model_validate(product)


@router.patch("/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: uuid.UUID,
    data: ProductUpdate,
    db: DbSession,
    current_user: SuperAdmin,
):
    repo = ProductRepository(db)
    product = await repo.get(product_id)
    if not product or product.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(product, k, v)
    await db.flush()
    return ProductOut.model_validate(product)


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: uuid.UUID,
    db: DbSession,
    current_user: SuperAdmin,
):
    repo = ProductRepository(db)
    product = await repo.get(product_id)
    if not product or product.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    await repo.soft_delete(product)
