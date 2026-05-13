"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useLocale } from "next-intl";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import Shell from "@/components/layout/shell";
import { inventoryApi, productsApi, branchesApi } from "@/lib/api";
import { Loader2, ChevronRight } from "lucide-react";
import Link from "next/link";

const schema = z.object({
  branch_id: z.string().uuid("اختر الفرع"),
  product_id: z.string().uuid("اختر المنتج"),
  batch_number: z.string().min(1, "رقم الدفعة مطلوب"),
  quantity: z.coerce.number().int().min(1, "الكمية يجب أن تكون أكثر من 0"),
  unit_cost: z.coerce.number().optional(),
  expiry_date: z.string().min(1, "تاريخ الانتهاء مطلوب"),
  manufacture_date: z.string().optional(),
  received_date: z.string().optional(),
  supplier: z.string().optional(),
  purchase_order_number: z.string().optional(),
  storage_condition_status: z.string().default("compliant"),
  notes: z.string().optional(),
});

type BatchForm = z.infer<typeof schema>;

const inputCls =
  "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";

export default function NewBatchPage() {
  const locale = useLocale();
  const router = useRouter();

  const { data: branches } = useQuery({
    queryKey: ["branches"],
    queryFn: () => branchesApi.list({ active_only: true }).then((r) => r.data),
  });

  const { data: products } = useQuery({
    queryKey: ["products"],
    queryFn: () => productsApi.list({ page_size: 100 }).then((r) => r.data),
  });

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<BatchForm>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: BatchForm) => {
    try {
      await inventoryApi.createBatch(data);
      toast.success("تم إضافة الدفعة بنجاح");
      router.push(`/${locale}/inventory/batches`);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(typeof msg === "string" ? msg : "فشل إضافة الدفعة");
    }
  };

  return (
    <Shell>
      <div className="max-w-2xl space-y-6">
        <div className="flex items-center gap-3">
          <Link
            href={`/${locale}/inventory/batches`}
            className="text-gray-500 hover:text-gray-700"
          >
            <ChevronRight className="h-5 w-5" />
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">إضافة دفعة جديدة</h1>
        </div>

        <form
          onSubmit={handleSubmit(onSubmit)}
          className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 space-y-4"
        >
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">الفرع *</label>
              <select {...register("branch_id")} className={inputCls}>
                <option value="">اختر الفرع</option>
                {branches?.items?.map((b: { id: string; name: string }) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
              {errors.branch_id && (
                <p className="text-red-500 text-xs mt-1">{errors.branch_id.message}</p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">المنتج *</label>
              <select {...register("product_id")} className={inputCls}>
                <option value="">اختر المنتج</option>
                {products?.items?.map((p: { id: string; name_ar: string; sku: string }) => (
                  <option key={p.id} value={p.id}>
                    {p.name_ar} ({p.sku})
                  </option>
                ))}
              </select>
              {errors.product_id && (
                <p className="text-red-500 text-xs mt-1">{errors.product_id.message}</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">رقم الدفعة *</label>
              <input {...register("batch_number")} className={inputCls} placeholder="BTH-XXXX" dir="ltr" />
              {errors.batch_number && (
                <p className="text-red-500 text-xs mt-1">{errors.batch_number.message}</p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">الكمية *</label>
              <input {...register("quantity")} type="number" min={1} className={inputCls} />
              {errors.quantity && (
                <p className="text-red-500 text-xs mt-1">{errors.quantity.message}</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                تاريخ انتهاء الصلاحية *
              </label>
              <input {...register("expiry_date")} type="date" className={inputCls} dir="ltr" />
              {errors.expiry_date && (
                <p className="text-red-500 text-xs mt-1">{errors.expiry_date.message}</p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                تاريخ التصنيع
              </label>
              <input {...register("manufacture_date")} type="date" className={inputCls} dir="ltr" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">سعر الوحدة</label>
              <input
                {...register("unit_cost")}
                type="number"
                step="0.01"
                min={0}
                placeholder="0.00"
                className={inputCls}
                dir="ltr"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">المورد</label>
              <input {...register("supplier")} className={inputCls} placeholder="اسم المورد" />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              حالة التخزين
            </label>
            <select {...register("storage_condition_status")} className={inputCls}>
              <option value="compliant">متوافق</option>
              <option value="non_compliant">غير متوافق</option>
              <option value="under_review">قيد المراجعة</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">ملاحظات</label>
            <textarea {...register("notes")} rows={3} className={inputCls} placeholder="ملاحظات اختيارية..." />
          </div>

          <div className="flex gap-3 pt-2">
            <Link
              href={`/${locale}/inventory/batches`}
              className="flex-1 border border-gray-300 text-gray-700 font-medium py-2.5 rounded-lg text-center hover:bg-gray-50"
            >
              إلغاء
            </Link>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 rounded-lg flex items-center justify-center gap-2 disabled:opacity-60"
            >
              {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
              إضافة الدفعة
            </button>
          </div>
        </form>
      </div>
    </Shell>
  );
}
