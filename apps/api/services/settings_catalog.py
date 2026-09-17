"""
What each platform setting means, in both languages.

The settings table stores a key and a JSON value, which is right for storage and
useless on a screen: an administrator sees `marketplace.platform_fee_pct` and a
raw object, and cannot tell whether 2 means two percent or two riyals. This is
the presentation layer for those rows — kept on the server so the API is the one
place that describes them, rather than every client inventing its own labels.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SettingSpec:
    label_ar: str
    label_en: str
    description_ar: str
    description_en: str
    value_type: str            # number | percent | boolean | text
    group_ar: str
    group_en: str
    unit_ar: str | None = None
    minimum: float | None = None
    maximum: float | None = None


CATALOG: dict[str, SettingSpec] = {
    "marketplace.platform_fee_pct": SettingSpec(
        label_ar="عمولة المنصة",
        label_en="Platform fee",
        description_ar=(
            "النسبة التي تحصلها المنصة من قيمة كل عملية بيع مكتملة. "
            "تغييرها يسري على العمليات الجديدة فقط."
        ),
        description_en=(
            "The percentage the platform takes from each completed sale. "
            "Changes apply to new transactions only."
        ),
        value_type="percent",
        group_ar="الرسوم والعمولات",
        group_en="Fees",
        unit_ar="٪",
        minimum=0,
        maximum=100,
    ),
    "marketplace.min_listing_days": SettingSpec(
        label_ar="أقل مدة متبقية للإدراج",
        label_en="Minimum days before expiry to list",
        description_ar=(
            "لا يسمح بإدراج دواء في السوق إذا تبقى على انتهائه أقل من هذا "
            "العدد من الأيام. يحمي المشتري من شراء ما لا يكفيه وقته."
        ),
        description_en=(
            "A medicine cannot be listed if fewer than this many days remain "
            "before it expires."
        ),
        value_type="number",
        group_ar="قواعد الإدراج",
        group_en="Listing rules",
        unit_ar="يوم",
        minimum=1,
        maximum=730,
    ),
    "listings.max_per_org": SettingSpec(
        label_ar="أقصى عدد عروض نشطة للمنشأة",
        label_en="Maximum active listings per pharmacy",
        description_ar=(
            "سقف العروض المنشورة في وقت واحد لكل منشأة. يمنع إغراق السوق "
            "من جهة واحدة."
        ),
        description_en=(
            "How many listings one pharmacy may have live at once."
        ),
        value_type="number",
        group_ar="قواعد الإدراج",
        group_en="Listing rules",
        unit_ar="عرض",
        minimum=1,
        maximum=10000,
    ),
    "notifications.email_enabled": SettingSpec(
        label_ar="إشعارات البريد الإلكتروني",
        label_en="Email notifications",
        description_ar=(
            "إرسال الإشعارات بالبريد إضافة إلى داخل المنصة. "
            "يتطلب ضبط مزود البريد في إعدادات الخادم."
        ),
        description_en=(
            "Send notifications by email as well as in-app. Requires an email "
            "provider to be configured on the server."
        ),
        value_type="boolean",
        group_ar="الإشعارات",
        group_en="Notifications",
    ),
    "notifications.whatsapp_enabled": SettingSpec(
        label_ar="إشعارات واتساب",
        label_en="WhatsApp notifications",
        description_ar=(
            "إرسال الإشعارات عبر واتساب. يتطلب ربط حساب واتساب للأعمال."
        ),
        description_en=(
            "Send notifications over WhatsApp. Requires a WhatsApp Business "
            "account to be connected."
        ),
        value_type="boolean",
        group_ar="الإشعارات",
        group_en="Notifications",
    ),
    "billing.grace_period_days": SettingSpec(
        label_ar="مهلة سداد الاشتراك",
        label_en="Subscription grace period",
        description_ar=(
            "عدد الأيام التي يبقى فيها الاشتراك فعالا بعد فشل عملية الدفع "
            "قبل أن يتحول إلى منتهي."
        ),
        description_en=(
            "How many days a subscription stays active after a failed payment "
            "before it expires."
        ),
        value_type="number",
        group_ar="الاشتراكات",
        group_en="Billing",
        unit_ar="يوم",
        minimum=0,
        maximum=30,
    ),
    "billing.proration_policy": SettingSpec(
        label_ar="سياسة التناسب عند ترقية الباقة",
        label_en="Proration policy",
        description_ar=(
            "كيف تحتسب قيمة الفترة المتبقية عند الترقية الفورية: "
            "immediate_prorated يحاسب الفرق عن الأيام المتبقية فقط."
        ),
        description_en=(
            "How upgrades bill the remainder of the current period: "
            "immediate_prorated charges the difference for the days left only."
        ),
        value_type="text",
        group_ar="الاشتراكات",
        group_en="Billing",
    ),
    "restock.demand_window_days": SettingSpec(
        label_ar="نافذة حساب الطلب",
        label_en="Demand window",
        description_ar=(
            "عدد الأيام التي تحسب منها سرعة الصرف عند توليد توصيات إعادة التوريد."
        ),
        description_en=(
            "How many days of dispense history the velocity calculation uses."
        ),
        value_type="number",
        group_ar="إعادة التوريد",
        group_en="Restock",
        unit_ar="يوم",
        minimum=7,
        maximum=365,
    ),
    "restock.lead_time_days": SettingSpec(
        label_ar="مهلة توريد افتراضية",
        label_en="Assumed supplier lead time",
        description_ar=(
            "مهلة التوريد المفترضة عند عدم وجود بيانات فعلية من المورد."
        ),
        description_en=(
            "Lead time assumed when no supplier data exists."
        ),
        value_type="number",
        group_ar="إعادة التوريد",
        group_en="Restock",
        unit_ar="يوم",
        minimum=0,
        maximum=60,
    ),
    "restock.safety_stock_days": SettingSpec(
        label_ar="أيام المخزون الاحترازي",
        label_en="Safety stock days",
        description_ar=(
            "أيام تغطية إضافية فوق مهلة التوريد عند حساب نقطة إعادة الطلب."
        ),
        description_en=(
            "Extra cover days on top of lead time in the reorder-point calculation."
        ),
        value_type="number",
        group_ar="إعادة التوريد",
        group_en="Restock",
        unit_ar="يوم",
        minimum=0,
        maximum=60,
    ),
    "restock.review_period_days": SettingSpec(
        label_ar="فترة المراجعة الدورية",
        label_en="Review period",
        description_ar=(
            "المدة بين مراجعتين متتاليتين للمخزون، وتدخل في حساب المخزون المستهدف."
        ),
        description_en=(
            "Time between two stock reviews; feeds the target-stock calculation."
        ),
        value_type="number",
        group_ar="إعادة التوريد",
        group_en="Restock",
        unit_ar="يوم",
        minimum=1,
        maximum=90,
    ),
    "restock.min_evidence_days": SettingSpec(
        label_ar="أقل مدة بيانات للتوصية",
        label_en="Minimum evidence days",
        description_ar=(
            "أقل عدد أيام من سجل الصرف قبل أن تعتبر البيانات كافية لاقتراح كمية."
        ),
        description_en=(
            "Dispense history shorter than this marks the recommendation as "
            "insufficient evidence and no quantity is suggested."
        ),
        value_type="number",
        group_ar="إعادة التوريد",
        group_en="Restock",
        unit_ar="يوم",
        minimum=1,
        maximum=90,
    ),
    "restock.min_buy_shelf_life_days": SettingSpec(
        label_ar="أقل صلاحية متبقية للشراء",
        label_en="Minimum shelf life when buying",
        description_ar=(
            "لا تقترح المنصة شراء عرض من السوق إذا كانت صلاحيته المتبقية أقل من هذا العدد."
        ),
        description_en=(
            "A marketplace listing is only suggested for replenishment when at "
            "least this many days of shelf life remain."
        ),
        value_type="number",
        group_ar="إعادة التوريد",
        group_en="Restock",
        unit_ar="يوم",
        minimum=0,
        maximum=365,
    ),
    "restock.dismiss_cooldown_days": SettingSpec(
        label_ar="مهلة إعادة توليد التوصية المرفوضة",
        label_en="Dismiss cooldown",
        description_ar=(
            "عدد الأيام التي لا تعاد فيها توليد توصية رفضها المستخدم ما لم تتغير مدخلاتها."
        ),
        description_en=(
            "A dismissed recommendation is not regenerated for this many days "
            "unless its input signature changes."
        ),
        value_type="number",
        group_ar="إعادة التوريد",
        group_en="Restock",
        unit_ar="يوم",
        minimum=0,
        maximum=90,
    ),
}

FALLBACK_GROUP_AR = "إعدادات أخرى"
FALLBACK_GROUP_EN = "Other"


def unwrap(value: object) -> object:
    """Settings are stored as {"value": x}; screens want the x."""
    if isinstance(value, dict) and set(value.keys()) == {"value"}:
        return value["value"]
    return value


def normalise_for_display(key: str, value: object) -> object:
    """Bring a stored value in line with its declared type, where it can be.

    A setting edited before the types were enforced can hold the wrong kind of
    value — a percentage stored as a boolean, say. Coercing on read keeps the
    screen showing a number rather than "True ٪", and leaves the administrator
    able to correct it. A value too far gone to convert is returned untouched
    rather than hidden.
    """
    try:
        return coerce(key, value)
    except (ValueError, TypeError):
        return value


def describe(key: str, raw_value: object, description: str | None) -> dict:
    """A setting row as a screen can present it, in Arabic and English."""
    spec = CATALOG.get(key)
    value = normalise_for_display(key, unwrap(raw_value))

    if spec is None:
        # An unknown key is still shown rather than hidden, so a setting added
        # later never disappears from the screen just for lacking a label.
        inferred = (
            "boolean" if isinstance(value, bool)
            else "number" if isinstance(value, (int, float))
            else "text"
        )
        return {
            "value": value,
            "label_ar": key,
            "label_en": key,
            "description_ar": description or "",
            "description_en": description or "",
            "value_type": inferred,
            "group_ar": FALLBACK_GROUP_AR,
            "group_en": FALLBACK_GROUP_EN,
            "unit_ar": None,
            "minimum": None,
            "maximum": None,
        }

    return {
        "value": value,
        "label_ar": spec.label_ar,
        "label_en": spec.label_en,
        "description_ar": spec.description_ar,
        "description_en": spec.description_en or description or "",
        "value_type": spec.value_type,
        "group_ar": spec.group_ar,
        "group_en": spec.group_en,
        "unit_ar": spec.unit_ar,
        "minimum": spec.minimum,
        "maximum": spec.maximum,
    }


def coerce(key: str, value: object) -> object:
    """Bring a submitted value to the type the setting is meant to hold."""
    spec = CATALOG.get(key)
    if spec is None:
        return value

    if spec.value_type == "boolean":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "نعم"}

    if spec.value_type in {"number", "percent"}:
        try:
            number = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{spec.label_ar}: القيمة يجب أن تكون رقما") from exc
        if spec.minimum is not None and number < spec.minimum:
            raise ValueError(f"{spec.label_ar}: أقل قيمة مسموحة {spec.minimum:g}")
        if spec.maximum is not None and number > spec.maximum:
            raise ValueError(f"{spec.label_ar}: أعلى قيمة مسموحة {spec.maximum:g}")
        # Keep whole numbers whole; "30.0 يوم" reads as a mistake.
        return int(number) if number == int(number) else number

    return str(value)
