"use client";

/**
 * The integration guide.
 *
 * Written for the person on the customer's side who has to make this work — so
 * it opens with three concrete steps and a request they can paste, and every
 * example is complete rather than a fragment. Arabic prose, LTR code.
 */

import { useState } from "react";
import Link from "next/link";
import { useLocale } from "next-intl";
import { Check, Copy, KeyRound, Terminal } from "lucide-react";

import Shell from "@/components/layout/shell";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ??
  "https://pharmacy-api-w1vu.onrender.com/api/v1";

function CodeBlock({ code, label }: { code: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* the block is selectable either way */
    }
  };

  return (
    <div className="rounded-xl overflow-hidden ring-1 ring-[#2c3a32] bg-[#1f2a24] my-3">
      <div className="flex items-center justify-between px-4 py-2 border-b border-[#2c3a32]">
        <span className="text-xs font-medium text-[#9fb3a6] flex items-center gap-1.5">
          <Terminal className="h-3.5 w-3.5" />
          {label ?? "طلب"}
        </span>
        <button
          type="button"
          onClick={copy}
          className="inline-flex items-center gap-1.5 text-xs text-[#9fb3a6] hover:text-white transition-colors"
        >
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? "تم النسخ" : "نسخ"}
        </button>
      </div>
      <pre dir="ltr" className="overflow-x-auto px-4 py-3.5 text-[13px] leading-relaxed">
        <code className="text-[#e8f0ea] font-mono whitespace-pre">{code}</code>
      </pre>
    </div>
  );
}

function Field({
  name,
  type,
  required,
  note,
}: {
  name: string;
  type: string;
  required?: boolean;
  note: string;
}) {
  return (
    <tr className="border-b border-[#eadfcc] last:border-0">
      <td className="py-2.5 px-3 align-top">
        <code dir="ltr" className="text-[13px] font-mono text-[#1f2a24]">
          {name}
        </code>
      </td>
      <td className="py-2.5 px-3 align-top">
        <code dir="ltr" className="text-xs text-[#8a9089] font-mono">
          {type}
        </code>
      </td>
      <td className="py-2.5 px-3 align-top whitespace-nowrap">
        {required ? (
          <span className="text-xs text-red-700 font-medium">إلزامي</span>
        ) : (
          <span className="text-xs text-[#a8927a]">اختياري</span>
        )}
      </td>
      <td className="py-2.5 px-3 align-top text-sm text-[#5f665f] leading-relaxed">
        {note}
      </td>
    </tr>
  );
}

const SECTIONS = [
  { id: "start", label: "البدء" },
  { id: "auth", label: "المصادقة" },
  { id: "endpoints", label: "النقاط" },
  { id: "sync", label: "إرسال المخزون" },
  { id: "near-expiry", label: "قرب الانتهاء" },
  { id: "odoo", label: "مثال أودو" },
  { id: "errors", label: "الأخطاء" },
];

export default function IntegrationDocsPage() {
  const locale = useLocale();

  return (
    <Shell>
      <div className="space-y-6">
        <PageHeader
          title="دليل الربط البرمجي"
          subtitle="اربط نظامك بمخزونك في MedSave — إرسال الأصناف وقراءة ما يقترب انتهاؤه"
          actions={
            <Link
              href={`/${locale}/org/api-keys`}
              className="inline-flex items-center gap-2 h-9 px-4 rounded-full bg-brand-600 text-white text-sm font-medium hover:bg-brand-700"
            >
              <KeyRound className="h-4 w-4" />
              إنشاء مفتاح
            </Link>
          }
        />

        {/* ── In-page navigation ──────────────────────────────────────── */}
        {/* Opaque, not translucent: the page is long and content scrolls
            underneath, and a see-through bar reads as a rendering fault. */}
        <nav className="flex flex-wrap gap-2 sticky top-2 z-10 bg-[#fffdf9] rounded-full px-2 py-2 ring-1 ring-[#e1d3c0] shadow-soft">
          {SECTIONS.map((section) => (
            <a
              key={section.id}
              href={`#${section.id}`}
              className="px-3.5 py-1.5 rounded-full text-sm text-[#5f665f] hover:bg-white hover:text-[#1f2a24] transition-colors"
            >
              {section.label}
            </a>
          ))}
        </nav>

        {/* ── Three steps ─────────────────────────────────────────────── */}
        <SectionCard
          title="ابدأ في ثلاث خطوات"
          subtitle="من صفر إلى أول مزامنة ناجحة"
        >
          <ol className="space-y-4">
            {[
              {
                title: "أنشئ مفتاحا",
                body: (
                  <>
                    من صفحة{" "}
                    <Link
                      href={`/${locale}/org/api-keys`}
                      className="text-brand-700 hover:text-brand-800 underline underline-offset-2"
                    >
                      مفاتيح الربط
                    </Link>
                    ، وامنحه <code className="text-xs">inventory:write</code> إن كان
                    سيرسل مخزونا و<code className="text-xs">inventory:read</code> إن
                    كان سيقرأ. المفتاح يعرض مرة واحدة فقط — احفظه في إعدادات نظامك،
                    لا في الكود.
                  </>
                ),
              },
              {
                title: "تحقق أن المفتاح يعمل",
                body: (
                  <>
                    ناد <code className="text-xs">/external/health</code>. إن رجع اسم
                    منشأتك فالربط سليم.
                  </>
                ),
              },
              {
                title: "أرسل أول دفعة",
                body: (
                  <>
                    ابدأ بصنف واحد للتأكد من الشكل، ثم أرسل الباقي على دفعات حتى ٥٠٠
                    صنف في الطلب الواحد.
                  </>
                ),
              },
            ].map((step, index) => (
              <li key={step.title} className="flex gap-4">
                <span className="shrink-0 h-8 w-8 rounded-full bg-brand-600 text-white text-sm font-semibold flex items-center justify-center">
                  {index + 1}
                </span>
                <div className="pt-1">
                  <h3 className="font-semibold text-[#1f2a24] mb-1">{step.title}</h3>
                  <p className="text-sm text-[#5f665f] leading-relaxed">{step.body}</p>
                </div>
              </li>
            ))}
          </ol>

          <div className="mt-5 rounded-xl bg-[#f4eadf] px-4 py-3">
            <p className="text-sm text-[#7b5411] leading-relaxed">
              <strong>لا تريد الربط البرمجي؟</strong> يمكنك رفع{" "}
              <Link
                href={`/${locale}/inventory/import`}
                className="underline underline-offset-2"
              >
                ملف Excel
              </Link>{" "}
              بدلا منه — النتيجة نفسها تماما.
            </p>
          </div>
        </SectionCard>

        {/* ── Authentication ──────────────────────────────────────────── */}
        <SectionCard
          title="المصادقة"
          subtitle="مفتاح واحد في ترويسة كل طلب"
        >
          <div id="auth" className="scroll-mt-24">
            <p className="text-sm text-[#5f665f] leading-relaxed">
              أرسل المفتاح في ترويسة <code className="text-xs">X-API-Key</code>. لا
              حاجة لتسجيل دخول ولا لجلسة، والمفتاح وحده يحدد منشأتك — لذلك لا يوجد
              أي معرف منشأة في أي طلب: لا يمكنك الوصول إلى بيانات منشأة أخرى ولا
              يمكن لأحد الوصول إلى بياناتك.
            </p>

            <CodeBlock
              label="التحقق من المفتاح"
              code={`curl -X GET "${API_BASE}/external/health" \\
  -H "X-API-Key: msk_live_xxxxxxxxxxxxxxxxxxxxx"`}
            />

            <CodeBlock
              label="الاستجابة"
              code={`{
  "status": "ok",
  "organization_id": "3f1c...",
  "organization_name": "صيدلية الدواء",
  "scopes": ["inventory:read", "inventory:write"],
  "server_time": "2026-08-14T09:12:44.183Z"
}`}
            />

            <div className="rounded-xl bg-amber-50 ring-1 ring-inset ring-amber-200 px-4 py-3 mt-4">
              <p className="text-sm text-amber-900 leading-relaxed">
                نحفظ بصمة مشفرة للمفتاح فقط ولا نحتفظ بنصه، فلا يمكننا استرجاعه لك.
                إن تسرب المفتاح، ألغه من صفحة المفاتيح — يتوقف عن العمل فورا — ثم
                أنشئ غيره.
              </p>
            </div>
          </div>
        </SectionCard>

        {/* ── Endpoint table ──────────────────────────────────────────── */}
        <SectionCard title="المسارات المتاحة" noPadding>
          <div id="endpoints" className="scroll-mt-24 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[#fdfbf7] text-[#8a9089]">
                <tr>
                  <th className="text-right font-medium px-5 py-2.5">النقطة</th>
                  <th className="text-right font-medium px-3 py-2.5">الصلاحية</th>
                  <th className="text-right font-medium px-3 py-2.5">الوظيفة</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#eadfcc]">
                {[
                  [
                    "GET /external/health",
                    "inventory:read",
                    "التحقق من صحة المفتاح ومعرفة المنشأة التي يتبعها.",
                  ],
                  [
                    "POST /external/inventory/sync",
                    "inventory:write",
                    "إرسال دفعة أصناف — تضاف الجديدة وتحدث الموجودة.",
                  ],
                  [
                    "GET /external/inventory/near-expiry",
                    "inventory:read",
                    "الأصناف التي يقترب انتهاؤها مع الأيام المتبقية.",
                  ],
                  [
                    "GET /external/listings",
                    "listings:read",
                    "عروضك المنشورة في السوق وحالتها.",
                  ],
                ].map(([endpoint, scope, purpose]) => (
                  <tr key={endpoint} className="hover:bg-[#fdfbf7]">
                    <td className="px-5 py-3">
                      <code dir="ltr" className="text-[13px] font-mono text-[#1f2a24]">
                        {endpoint}
                      </code>
                    </td>
                    <td className="px-3 py-3">
                      <code
                        dir="ltr"
                        className="text-xs px-2 py-0.5 rounded bg-[#f4eadf] text-[#7b5411] font-mono"
                      >
                        {scope}
                      </code>
                    </td>
                    <td className="px-3 py-3 text-[#5f665f] leading-relaxed">
                      {purpose}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="px-5 py-3 text-xs text-[#8a9089] border-t border-[#eadfcc]">
              العنوان الأساسي:{" "}
              <code dir="ltr" className="font-mono">
                {API_BASE}
              </code>
            </p>
          </div>
        </SectionCard>

        {/* ── Sync ────────────────────────────────────────────────────── */}
        <SectionCard
          title="إرسال المخزون"
          subtitle="POST /external/inventory/sync"
        >
          <div id="sync" className="scroll-mt-24">
            <p className="text-sm text-[#5f665f] leading-relaxed mb-4">
              أرسل حتى ٥٠٠ صنف في الطلب الواحد. التكرار آمن: إذا أرسلت الصنف نفسه
              مرة أخرى — نفس الفرع ونفس الدواء ونفس رقم التشغيلة — تحدث الكمية ولا
              تضاف تشغيلة ثانية. لذلك يصلح هذا الطلب لمزامنة يومية مجدولة.
            </p>

            <div className="overflow-x-auto rounded-xl ring-1 ring-[#eadfcc]">
              <table className="w-full">
                <thead className="bg-[#fdfbf7] text-[#8a9089] text-xs">
                  <tr>
                    <th className="text-right font-medium px-3 py-2">الحقل</th>
                    <th className="text-right font-medium px-3 py-2">النوع</th>
                    <th className="text-right font-medium px-3 py-2">الإلزام</th>
                    <th className="text-right font-medium px-3 py-2">ملاحظات</th>
                  </tr>
                </thead>
                <tbody>
                  <Field
                    name="product_name"
                    type="string"
                    required
                    note="اسم الدواء عربي أو إنجليزي. نطابقه مع كتالوجنا، وما لا نتعرف عليه ينشأ كمنتج خاص بمنشأتك."
                  />
                  <Field
                    name="batch_number"
                    type="string"
                    required
                    note="رقم التشغيلة. هو مفتاح التحديث لاحقا، فحافظ على ثباته."
                  />
                  <Field
                    name="expiry_date"
                    type="string (YYYY-MM-DD)"
                    required
                    note="تاريخ انتهاء الصلاحية."
                  />
                  <Field
                    name="quantity"
                    type="integer ≥ 0"
                    required
                    note="الكمية الحالية. ما نستقبله يصبح هو الرقم المعتمد."
                  />
                  <Field
                    name="barcode"
                    type="string"
                    note="الباركود أو GTIN. أدق وسيلة للمطابقة — أرسله متى توفر."
                  />
                  <Field
                    name="sku"
                    type="string"
                    note="كودك الداخلي للمنتج. يبقى مرجعك ولا يتعارض مع أكواد المنشآت الأخرى."
                  />
                  <Field
                    name="branch_name"
                    type="string"
                    note="اسم الفرع كما هو مسجل لديك في المنصة. إن كان لديك فرع واحد فقط يمكن تركه فارغا."
                  />
                  <Field name="unit_cost" type="number ≥ 0" note="سعر التكلفة للوحدة." />
                  <Field
                    name="requires_cold_chain"
                    type="boolean"
                    note="هل يحتاج الصنف سلسلة تبريد."
                  />
                  <Field
                    name="supplier · purchase_order_number · notes"
                    type="string"
                    note="بيانات مرجعية تحفظ كما هي."
                  />
                </tbody>
              </table>
            </div>

            <CodeBlock
              label="curl"
              code={`curl -X POST "${API_BASE}/external/inventory/sync" \\
  -H "X-API-Key: msk_live_xxxxxxxxxxxxxxxxxxxxx" \\
  -H "Content-Type: application/json" \\
  -d '{
    "items": [
      {
        "product_name": "Amoxicillin 500mg",
        "barcode": "6281000123456",
        "sku": "AMX-500",
        "batch_number": "B-2026-114",
        "expiry_date": "2026-11-30",
        "quantity": 240,
        "unit_cost": 12.50,
        "branch_name": "الفرع الرئيسي"
      }
    ]
  }'`}
            />

            <CodeBlock
              label="الاستجابة"
              code={`{
  "job_id": "9c1e...",
  "received": 1,
  "created_batches": 1,
  "updated_batches": 0,
  "created_products": 0,
  "matched_products": 1,
  "failed": 0,
  "errors": []
}`}
            />

            <p className="text-sm text-[#5f665f] leading-relaxed mt-4">
              الصنف الفاسد لا يسقط الدفعة: تقبل بقية الأصناف، ويعود الفاشل في{" "}
              <code className="text-xs">errors</code> مع{" "}
              <code className="text-xs">index</code> يدل على موقعه في المصفوفة التي
              أرسلتها.
            </p>

            <CodeBlock
              label="Python"
              code={`import requests

API = "${API_BASE}"
KEY = "msk_live_xxxxxxxxxxxxxxxxxxxxx"

def sync(items):
    """Send stock in batches of 500."""
    for start in range(0, len(items), 500):
        chunk = items[start:start + 500]
        response = requests.post(
            f"{API}/external/inventory/sync",
            headers={"X-API-Key": KEY},
            json={"items": chunk},
            timeout=120,
        )
        response.raise_for_status()
        result = response.json()
        print(f"{result['created_batches']} added, "
              f"{result['updated_batches']} updated, "
              f"{result['failed']} failed")
        for error in result["errors"]:
            print(f"  item {error['index']}: {error['reason']}")`}
            />
          </div>
        </SectionCard>

        {/* ── Near expiry ─────────────────────────────────────────────── */}
        <SectionCard
          title="قراءة ما يقترب انتهاؤه"
          subtitle="GET /external/inventory/near-expiry"
        >
          <div id="near-expiry" className="scroll-mt-24">
            <p className="text-sm text-[#5f665f] leading-relaxed mb-3">
              المعاملان <code className="text-xs">within_days</code> (افتراضيا ١٨٠)
              و<code className="text-xs">limit</code> (افتراضيا ٢٠٠). النتيجة مرتبة
              بالأقرب انتهاء أولا.
            </p>

            <CodeBlock
              label="curl"
              code={`curl -X GET "${API_BASE}/external/inventory/near-expiry?within_days=90" \\
  -H "X-API-Key: msk_live_xxxxxxxxxxxxxxxxxxxxx"`}
            />

            <CodeBlock
              label="الاستجابة"
              code={`{
  "total": 2,
  "within_days": 90,
  "items": [
    {
      "batch_id": "1a2b...",
      "product_name": "Amoxicillin 500mg",
      "batch_number": "B-2026-114",
      "branch_name": "الفرع الرئيسي",
      "expiry_date": "2026-09-02",
      "days_remaining": 19,
      "quantity_available": 240,
      "zone": "red"
    }
  ]
}`}
            />

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-4">
              {[
                ["red", "أقل من ٣٠ يوما", "bg-red-50 text-red-700 ring-red-200"],
                ["orange", "٣٠ – ٩٠ يوما", "bg-orange-50 text-orange-700 ring-orange-200"],
                ["yellow", "٩٠ – ١٨٠ يوما", "bg-amber-50 text-amber-800 ring-amber-200"],
                ["green", "أكثر من ١٨٠ يوما", "bg-emerald-50 text-emerald-700 ring-emerald-200"],
              ].map(([zone, label, style]) => (
                <div
                  key={zone}
                  className={`rounded-xl px-3 py-2.5 ring-1 ring-inset ${style}`}
                >
                  <code dir="ltr" className="text-xs font-mono font-semibold">
                    {zone}
                  </code>
                  <p className="text-xs mt-0.5">{label}</p>
                </div>
              ))}
            </div>
          </div>
        </SectionCard>

        {/* ── Odoo ────────────────────────────────────────────────────── */}
        <SectionCard
          title="مثال عملي: أودو"
          subtitle="قراءة التشغيلات من stock.lot وإرسالها يوميا"
        >
          <div id="odoo" className="scroll-mt-24">
            <p className="text-sm text-[#5f665f] leading-relaxed mb-3">
              في أودو ١٦ فما فوق، تواريخ الانتهاء موجودة على{" "}
              <code className="text-xs">stock.lot</code> والكميات على{" "}
              <code className="text-xs">stock.quant</code>. أضف الكود التالي ك
              <strong> Server Action</strong>، ثم اربطه ب
              <strong> Scheduled Action</strong> يومية.
            </p>

            <CodeBlock
              label="Odoo — Server Action (Python)"
              code={`import requests

API = "${API_BASE}"
KEY = env["ir.config_parameter"].sudo().get_param("medsave.api_key")

quants = env["stock.quant"].search([
    ("location_id.usage", "=", "internal"),
    ("lot_id", "!=", False),
    ("quantity", ">", 0),
])

items = []
for quant in quants:
    lot = quant.lot_id
    if not lot.expiration_date:
        continue
    items.append({
        "product_name": quant.product_id.name,
        "barcode": quant.product_id.barcode or None,
        "sku": quant.product_id.default_code or None,
        "batch_number": lot.name,
        "expiry_date": lot.expiration_date.strftime("%Y-%m-%d"),
        "quantity": int(quant.quantity),
        "unit_cost": quant.product_id.standard_price,
        "branch_name": quant.location_id.warehouse_id.name,
    })

for start in range(0, len(items), 500):
    response = requests.post(
        API + "/external/inventory/sync",
        headers={"X-API-Key": KEY},
        json={"items": items[start:start + 500]},
        timeout=120,
    )
    response.raise_for_status()`}
            />

            <div className="rounded-xl bg-[#fdfbf7] ring-1 ring-[#eadfcc] px-4 py-3 mt-3">
              <p className="text-sm text-[#5f665f] leading-relaxed">
                <strong className="text-[#1f2a24]">قبل التشغيل:</strong> احفظ المفتاح في{" "}
                <em>الإعدادات ← التقنية ← معاملات النظام</em> باسم{" "}
                <code dir="ltr" className="text-xs">
                  medsave.api_key
                </code>{" "}
                بدلا من كتابته في الكود، وتأكد أن أسماء المستودعات لديك تطابق أسماء
                فروعك في المنصة.
              </p>
            </div>
          </div>
        </SectionCard>

        {/* ── Errors ──────────────────────────────────────────────────── */}
        <SectionCard title="رموز الأخطاء" noPadding>
          <div id="errors" className="scroll-mt-24 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[#fdfbf7] text-[#8a9089]">
                <tr>
                  <th className="text-right font-medium px-5 py-2.5">الرمز</th>
                  <th className="text-right font-medium px-3 py-2.5">المعنى</th>
                  <th className="text-right font-medium px-3 py-2.5">ما تفعله</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#eadfcc]">
                {[
                  [
                    "401",
                    "المفتاح مفقود أو غير صالح أو ملغى.",
                    "تحقق من ترويسة X-API-Key، وأنشئ مفتاحا جديدا إن كان ملغى.",
                  ],
                  [
                    "403",
                    "المفتاح لا يملك الصلاحية المطلوبة، أو المنشأة غير معتمدة.",
                    "أنشئ مفتاحا بالصلاحية الصحيحة، أو راجع حالة اعتماد منشأتك.",
                  ],
                  [
                    "409",
                    "بلغ مخزونك الحد الأقصى (١٠٬٠٠٠ صنف).",
                    "احذف أصنافا منتهية، أو تواصل معنا لرفع الحد.",
                  ],
                  [
                    "422",
                    "شكل الطلب غير صحيح — حقل ناقص أو نوع خاطئ.",
                    "راجع جدول الحقول أعلاه؛ الرسالة تحدد الحقل.",
                  ],
                  [
                    "429",
                    "طلبات كثيرة في وقت قصير.",
                    "أرسل على دفعات أكبر وبتباعد أطول.",
                  ],
                ].map(([code, meaning, action]) => (
                  <tr key={code} className="hover:bg-[#fdfbf7]">
                    <td className="px-5 py-3">
                      <code
                        dir="ltr"
                        className="text-sm font-mono font-semibold text-[#1f2a24]"
                      >
                        {code}
                      </code>
                    </td>
                    <td className="px-3 py-3 text-[#5f665f] leading-relaxed">
                      {meaning}
                    </td>
                    <td className="px-3 py-3 text-[#5f665f] leading-relaxed">
                      {action}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>

        <div className="rounded-2xl bg-[#1f2a24] px-6 py-5 text-center">
          <p className="text-[#e8f0ea] text-sm leading-relaxed">
            واجهت مشكلة في الربط؟ راسلنا على{" "}
            <a
              href="mailto:support@medsave.sa"
              className="text-white underline underline-offset-2"
            >
              support@medsave.sa
            </a>{" "}
            مع رقم <code className="text-xs">job_id</code> من آخر استجابة — يكفي
            لتتبع ما حدث.
          </p>
        </div>
      </div>
    </Shell>
  );
}
