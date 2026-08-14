"""
Turning an uploaded spreadsheet into inventory batches.

The shape of this service follows three facts about the job:

* Ten thousand rows do not fit in an HTTP request, so the work happens in a
  worker and the customer polls a job row.
* One bad row must not cost the customer the other 9,999. Every row is validated
  on its own; failures are collected with their line number and the import
  carries on.
* The same file gets re-uploaded weekly as a sync. A batch is therefore keyed by
  (organization, branch, product, batch number) — a second upload updates the
  quantity instead of duplicating the stock.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models.branch import PharmacyBranch
from models.import_job import ImportJob, ImportStatus
from models.inventory import BatchStatus, InventoryBatch
from models.notification import NotificationType
from services import excel_service
from services.product_matching_service import ProductMatcher, normalise

logger = logging.getLogger("api.imports")

MAX_EXPIRY_YEARS = 20


class RowError(Exception):
    """A row that cannot be imported, with the reason the customer will read."""


async def count_org_items(db: AsyncSession, org_id: uuid.UUID) -> int:
    """How many live batches the pharmacy already holds."""
    return int(
        await db.scalar(
            select(func.count(InventoryBatch.id)).where(
                InventoryBatch.organization_id == org_id,
                InventoryBatch.deleted_at.is_(None),
            )
        )
        or 0
    )


class ImportProcessor:
    """Runs one import job to completion."""

    def __init__(self, db: AsyncSession, job: ImportJob) -> None:
        self.db = db
        self.job = job
        self.org_id = job.organization_id
        self.matcher = ProductMatcher(db, job.organization_id)
        self.errors: list[dict] = []
        self.branches: dict[str, uuid.UUID] = {}
        self.default_branch_id: uuid.UUID | None = None
        # Batches touched in this run, so two rows for the same batch in one
        # file add up rather than fighting each other.
        self.seen: dict[tuple[uuid.UUID, uuid.UUID, str], InventoryBatch] = {}
        self.created_products = 0
        self.matched_products = 0
        self.created_batches = 0
        self.updated_batches = 0

    # ── Setup ─────────────────────────────────────────────────────────────

    async def load_branches(self) -> None:
        rows = (
            await self.db.execute(
                select(PharmacyBranch).where(
                    PharmacyBranch.organization_id == self.org_id,
                    PharmacyBranch.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        for branch in rows:
            for label in (branch.name, branch.name_ar, branch.branch_code):
                key = normalise(label)
                if key:
                    self.branches.setdefault(key, branch.id)
        # A single-branch pharmacy should not have to name it in every row.
        if len(rows) == 1:
            self.default_branch_id = rows[0].id
        if not rows:
            raise ValueError("لا يوجد فرع مسجّل للمنشأة — أضف فرعاً قبل الاستيراد")

    # ── Per-row work ──────────────────────────────────────────────────────

    def resolve_branch(self, value: object) -> uuid.UUID:
        key = normalise(excel_service.clean_text(value))
        if not key:
            if self.default_branch_id:
                return self.default_branch_id
            raise RowError("الفرع مطلوب")
        branch_id = self.branches.get(key)
        if branch_id is None:
            raise RowError(f"الفرع غير معروف: {excel_service.clean_text(value)}")
        return branch_id

    def validate(self, row: excel_service.ParsedRow) -> dict:
        """Everything that can be judged from the row alone."""
        values = row.values

        name = excel_service.clean_text(values.get("product_name"))
        if not name:
            raise RowError("اسم الدواء مطلوب")

        batch_number = excel_service.clean_text(values.get("batch_number"))
        if not batch_number:
            raise RowError("رقم التشغيلة مطلوب")

        expiry = excel_service.coerce_date(values.get("expiry_date"))
        if expiry is None:
            raise RowError("تاريخ الانتهاء مطلوب بصيغة YYYY-MM-DD")
        today = date.today()
        if expiry.year > today.year + MAX_EXPIRY_YEARS:
            raise RowError("تاريخ الانتهاء غير منطقي — تحقّق من الصيغة")

        quantity = excel_service.coerce_int(values.get("quantity"))
        if quantity is None:
            raise RowError("الكمية مطلوبة كعدد صحيح")
        if quantity < 0:
            raise RowError("الكمية لا يمكن أن تكون سالبة")

        unit_cost = excel_service.coerce_float(values.get("unit_cost"))
        if unit_cost is not None and unit_cost < 0:
            raise RowError("سعر التكلفة لا يمكن أن يكون سالباً")

        return {
            "name": name,
            "barcode": excel_service.clean_text(values.get("barcode")),
            "sku": excel_service.clean_text(values.get("sku")),
            "batch_number": batch_number[:100],
            "expiry_date": expiry,
            "quantity": quantity,
            "unit_cost": unit_cost,
            "branch_id": self.resolve_branch(values.get("branch_name")),
            "supplier": excel_service.clean_text(values.get("supplier")),
            "purchase_order_number": excel_service.clean_text(
                values.get("purchase_order_number")
            ),
            "requires_cold_chain": excel_service.coerce_bool(
                values.get("requires_cold_chain")
            ),
            "notes": excel_service.clean_text(values.get("notes")),
        }

    async def resolve_product(self, data: dict) -> uuid.UUID:
        product_id, how = self.matcher.find(
            name=data["name"], barcode=data["barcode"], sku=data["sku"]
        )
        if product_id is not None:
            self.matched_products += 1
            logger.debug("Row matched by %s: %s", how, data["name"])
            return product_id

        product = await self.matcher.create_private_product(
            name=data["name"], barcode=data["barcode"], sku=data["sku"]
        )
        self.created_products += 1
        return product.id

    async def upsert_batch(self, data: dict, product_id: uuid.UUID) -> None:
        key = (data["branch_id"], product_id, data["batch_number"])

        existing = self.seen.get(key)
        if existing is None:
            existing = (
                await self.db.execute(
                    select(InventoryBatch).where(
                        InventoryBatch.organization_id == self.org_id,
                        InventoryBatch.branch_id == data["branch_id"],
                        InventoryBatch.product_id == product_id,
                        InventoryBatch.batch_number == data["batch_number"],
                        InventoryBatch.deleted_at.is_(None),
                    )
                )
            ).scalars().first()
            if existing is not None:
                self.updated_batches += 1

        if existing is not None:
            # A re-upload is a correction, not an addition: the file is the
            # source of truth for quantity. Only the part already sold or
            # reserved is protected.
            committed = max(existing.quantity - existing.quantity_available, 0)
            existing.quantity = data["quantity"]
            existing.quantity_available = max(data["quantity"] - committed, 0)
            existing.expiry_date = data["expiry_date"]
            if data["unit_cost"] is not None:
                existing.unit_cost = data["unit_cost"]
            if data["supplier"]:
                existing.supplier = data["supplier"][:255]
            if data["purchase_order_number"]:
                existing.purchase_order_number = data["purchase_order_number"][:100]
            if data["notes"]:
                existing.notes = data["notes"]
            existing.requires_cold_chain = data["requires_cold_chain"]
            self.seen[key] = existing
            return

        batch = InventoryBatch(
            id=uuid.uuid4(),
            organization_id=self.org_id,
            branch_id=data["branch_id"],
            product_id=product_id,
            batch_number=data["batch_number"],
            quantity=data["quantity"],
            quantity_available=data["quantity"],
            unit_cost=data["unit_cost"],
            expiry_date=data["expiry_date"],
            received_date=date.today(),
            supplier=(data["supplier"] or None) and data["supplier"][:255],
            purchase_order_number=(data["purchase_order_number"] or None)
            and data["purchase_order_number"][:100],
            requires_cold_chain=data["requires_cold_chain"],
            notes=data["notes"],
            status=(
                BatchStatus.EXPIRED
                if data["expiry_date"] <= date.today()
                else BatchStatus.ACTIVE
            ),
        )
        self.db.add(batch)
        self.created_batches += 1
        self.seen[key] = batch

    # ── The run ───────────────────────────────────────────────────────────

    def record_error(self, line_number: int, reason: str, row: dict | None = None) -> None:
        self.errors.append(
            {
                "line": line_number,
                "reason": reason,
                "product_name": (row or {}).get("product_name"),
                "batch_number": (row or {}).get("batch_number"),
            }
        )

    async def run(self, content: bytes, filename: str) -> None:
        """Import an uploaded file."""
        await self.run_rows(excel_service.read_rows(content, filename))

    async def run_rows(self, rows) -> None:
        """Import any stream of parsed rows — a spreadsheet or an API payload."""
        await self.load_branches()
        await self.matcher.load()

        existing_items = await count_org_items(self.db, self.org_id)
        ceiling = settings.MAX_INVENTORY_ITEMS_PER_ORG
        remaining = max(ceiling - existing_items, 0)
        capped = False

        processed = 0
        for row in rows:
            processed += 1
            try:
                data = self.validate(row)

                if self.created_batches >= remaining:
                    # Updating existing stock is always allowed; only genuinely
                    # new items are capped.
                    probe = await self._is_new_item(data)
                    if probe:
                        capped = True
                        self.record_error(
                            row.line_number,
                            f"تم بلوغ الحد الأقصى ({ceiling} صنف) — لم يُضف هذا الصف",
                            {
                                "product_name": data["name"],
                                "batch_number": data["batch_number"],
                            },
                        )
                        continue

                product_id = await self.resolve_product(data)
                await self.upsert_batch(data, product_id)
            except RowError as exc:
                self.record_error(
                    row.line_number,
                    str(exc),
                    {
                        "product_name": excel_service.clean_text(
                            row.values.get("product_name")
                        ),
                        "batch_number": excel_service.clean_text(
                            row.values.get("batch_number")
                        ),
                    },
                )
            except Exception as exc:  # a single row must never kill the file
                logger.exception("Row %d failed", row.line_number)
                self.record_error(row.line_number, f"خطأ غير متوقع: {exc}")

            if processed % settings.IMPORT_BATCH_SIZE == 0:
                await self.db.flush()
                self.job.processed_rows = processed
                self.job.total_rows = processed
                self.job.created_batches = self.created_batches
                self.job.updated_batches = self.updated_batches
                self.job.failed_rows = len(self.errors)
                await self.db.commit()
                logger.info("Import %s: %d rows", self.job.id, processed)

        await self.db.flush()
        self.job.total_rows = processed
        self.job.processed_rows = processed
        self.job.created_batches = self.created_batches
        self.job.updated_batches = self.updated_batches
        self.job.created_products = self.created_products
        self.job.matched_products = self.matched_products
        self.job.failed_rows = len(self.errors)
        self.job.errors = self.errors[: settings.IMPORT_MAX_INLINE_ERRORS]
        if capped:
            self.job.failure_reason = (
                f"تم بلوغ الحد الأقصى للمخزون ({ceiling} صنف). "
                "احذف أصنافاً منتهية أو تواصل معنا لرفع الحد."
            )
        self.job.status = (
            ImportStatus.COMPLETED_WITH_ERRORS if self.errors else ImportStatus.COMPLETED
        )
        self.job.finished_at = datetime.now(timezone.utc)

        if self.errors:
            self._write_error_file()

    async def _is_new_item(self, data: dict) -> bool:
        """Would this row create a batch rather than update one?"""
        product_id, _ = self.matcher.find(
            name=data["name"], barcode=data["barcode"], sku=data["sku"]
        )
        if product_id is None:
            return True
        if (data["branch_id"], product_id, data["batch_number"]) in self.seen:
            return False
        found = await self.db.scalar(
            select(InventoryBatch.id).where(
                InventoryBatch.organization_id == self.org_id,
                InventoryBatch.branch_id == data["branch_id"],
                InventoryBatch.product_id == product_id,
                InventoryBatch.batch_number == data["batch_number"],
                InventoryBatch.deleted_at.is_(None),
            )
        )
        return found is None

    def _write_error_file(self) -> None:
        from services.storage_service import storage_service

        try:
            content = excel_service.build_errors_workbook(self.errors)
            self.job.error_file_path = storage_service.save_bytes(
                content, self.org_id, f"errors-{self.job.id}.xlsx"
            )
        except Exception:
            # The report is a convenience; losing it must not fail the import,
            # since the first errors are on the job row regardless.
            logger.exception("Could not write the errors file for job %s", self.job.id)


async def process_job(db: AsyncSession, job: ImportJob) -> None:
    """Run a claimed job, recording failure on the job rather than raising."""
    from services.notification_service import NotificationService
    from services.storage_service import storage_service

    job.status = ImportStatus.PROCESSING
    job.started_at = datetime.now(timezone.utc)
    await db.commit()

    try:
        path = storage_service.resolve(job.stored_path or "")
        content = path.read_bytes()
        processor = ImportProcessor(db, job)
        await processor.run(content, job.filename)
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.exception("Import job %s failed", job.id)
        job.status = ImportStatus.FAILED
        job.failure_reason = str(exc)[:1000]
        job.finished_at = datetime.now(timezone.utc)
        await db.commit()

    if job.created_by_id:
        try:
            await NotificationService(db).create(
                user_id=job.created_by_id,
                organization_id=job.organization_id,
                notification_type=NotificationType.SYSTEM,
                title="Inventory import finished",
                title_ar="اكتمل استيراد المخزون",
                body=(
                    f"{job.created_batches} added, {job.updated_batches} updated, "
                    f"{job.failed_rows} failed."
                ),
                body_ar=(
                    f"تمت إضافة {job.created_batches} تشغيلة وتحديث "
                    f"{job.updated_batches}، وفشل {job.failed_rows} صف."
                ),
                resource_type="import_job",
                resource_id=job.id,
            )
            await db.commit()
        except Exception:
            logger.exception("Could not notify for import job %s", job.id)
            await db.rollback()
