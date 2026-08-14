"""
Matching a customer's medicine name onto a product record.

The catalogue is small and the names customers use are inconsistent — Arabic and
English, with and without strength, with Arabic-Indic digits. Matching therefore
runs in order of confidence: barcode first because it is unambiguous, then an
exact normalised name, then name plus strength. Anything still unmatched becomes
a product private to that pharmacy, so the import never stalls on vocabulary.
"""
from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.product import Product, ProductCategory, ProductSource

logger = logging.getLogger("api.matching")

ARABIC_INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
DIACRITICS = re.compile(r"[ؐ-ؚ-ٟ-]")
NON_ALNUM = re.compile(r"[^0-9a-zء-ي]+")

# Alef and yaa are written several ways; treat them as one letter for matching.
LETTER_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي"})


# The same dose is written a dozen ways; collapse the unit to one token so
# "500mg", "500 مجم" and "٥٠٠ملجم" all compare equal.
UNIT_SYNONYMS = {
    "ملجم": "mg", "مجم": "mg", "مليجرام": "mg", "ميلليجرام": "mg", "milligram": "mg",
    "مايكروجرام": "mcg", "ميكروجرام": "mcg", "microgram": "mcg", "µg": "mcg", "ug": "mcg",
    "جم": "g", "جرام": "g", "gram": "g",
    "مل": "ml", "ملل": "ml", "مليلتر": "ml", "millilitre": "ml", "milliliter": "ml",
    "وحدة": "iu", "وحدات": "iu",
}
DIGIT_LETTER = re.compile(r"(?<=\d)(?=[^\W\d])|(?<=[^\W\d])(?=\d)", re.UNICODE)


def normalise(name: str | None) -> str:
    """A comparable form of a medicine name."""
    if not name:
        return ""
    text = str(name).strip().lower().translate(ARABIC_INDIC)
    text = DIACRITICS.sub("", text)
    text = text.translate(LETTER_FOLD)
    # "500mg" and "500 mg" must reduce to the same thing.
    text = DIGIT_LETTER.sub(" ", text)
    text = NON_ALNUM.sub(" ", text)
    tokens = [UNIT_SYNONYMS.get(token, token) for token in text.split()]
    return " ".join(tokens)


def extract_strength(name: str | None) -> str | None:
    """The dose written into the name, e.g. "500mg" or "٥٠٠ مجم"."""
    if not name:
        return None
    text = str(name).lower().translate(ARABIC_INDIC)
    match = re.search(r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|iu|مجم|ملجم|جم|مل)", text)
    if not match:
        return None
    unit = match.group(2)
    canonical = {"ملجم": "mg", "مجم": "mg", "جم": "g", "مل": "ml"}.get(unit, unit)
    return f"{match.group(1)}{canonical}"


class ProductMatcher:
    """Caches the visible catalogue once per import rather than per row."""

    def __init__(self, db: AsyncSession, org_id: uuid.UUID) -> None:
        self.db = db
        self.org_id = org_id
        self._by_barcode: dict[str, uuid.UUID] = {}
        self._by_name: dict[str, uuid.UUID] = {}
        self._by_name_strength: dict[tuple[str, str], uuid.UUID] = {}
        self._by_sku: dict[str, uuid.UUID] = {}
        self._default_category_id: uuid.UUID | None = None
        self.loaded = False

    async def load(self) -> None:
        """Read the shared catalogue plus this pharmacy's own products."""
        from repositories.product import ProductRepository

        rows = (
            await self.db.execute(
                select(Product).where(
                    Product.deleted_at.is_(None),
                    ProductRepository.visible_to(self.org_id),
                )
            )
        ).scalars().all()

        for product in rows:
            if product.barcode:
                self._by_barcode.setdefault(str(product.barcode).strip(), product.id)
            if product.sku:
                self._by_sku.setdefault(normalise(product.sku), product.id)
            for candidate in (product.name, product.name_ar):
                key = normalise(candidate)
                if key:
                    self._by_name.setdefault(key, product.id)
                    strength = extract_strength(candidate)
                    if strength:
                        base = key.replace(normalise(strength), "").strip()
                        self._by_name_strength.setdefault((base, strength), product.id)

        category = (
            await self.db.execute(
                select(ProductCategory).order_by(ProductCategory.sort_order).limit(1)
            )
        ).scalar_one_or_none()
        self._default_category_id = category.id if category else None
        self.loaded = True
        logger.info(
            "Matcher loaded %d products for org %s", len(rows), self.org_id
        )

    def find(
        self, *, name: str | None, barcode: str | None, sku: str | None
    ) -> tuple[uuid.UUID | None, str]:
        """Returns (product id, how it matched)."""
        if barcode:
            hit = self._by_barcode.get(str(barcode).strip())
            if hit:
                return hit, "barcode"

        if sku:
            hit = self._by_sku.get(normalise(sku))
            if hit:
                return hit, "sku"

        key = normalise(name)
        if key:
            hit = self._by_name.get(key)
            if hit:
                return hit, "name"

            strength = extract_strength(name)
            if strength:
                base = key.replace(normalise(strength), "").strip()
                hit = self._by_name_strength.get((base, strength))
                if hit:
                    return hit, "name+strength"

        return None, "none"

    async def create_private_product(
        self, *, name: str, barcode: str | None, sku: str | None
    ) -> Product:
        """A product private to this pharmacy, flagged for catalogue review."""
        if self._default_category_id is None:
            raise ValueError("لا توجد فئة منتجات في النظام")

        # The customer's own code if given, otherwise a generated one that cannot
        # collide inside their namespace.
        code = (sku or "").strip() or f"IMP-{uuid.uuid4().hex[:10].upper()}"
        product = Product(
            id=uuid.uuid4(),
            owner_organization_id=self.org_id,
            is_draft=True,
            source=ProductSource.IMPORT,
            category_id=self._default_category_id,
            name=name[:255],
            name_ar=name[:255],
            sku=code[:100],
            barcode=(barcode or None) and str(barcode).strip()[:100],
        )
        self.db.add(product)
        await self.db.flush()

        # Register it so later rows in the same file reuse it instead of
        # creating a second copy.
        key = normalise(name)
        if key:
            self._by_name.setdefault(key, product.id)
        if product.barcode:
            self._by_barcode.setdefault(product.barcode, product.id)
        self._by_sku.setdefault(normalise(product.sku), product.id)
        return product
