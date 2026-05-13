"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useLocale } from "next-intl";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import Shell from "@/components/layout/shell";
import { listingsApi, inventoryApi } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import { ExpiryBadge } from "@/components/ui/expiry-badge";
import { CheckCircle, XCircle, Loader2, ChevronRight } from "lucide-react";
import Link from "next/link";

const listingSchema = z.object({
  batch_id: z.string().min(1, "يجب اختيار دفعة"),
  asking_price: z.coerce.number().min(0.01, "السعر مطلوب"),
  quantity_available: z.coerce.number().int().min(1, "الكمية مطلوبة"),
  minimum_offer_price: z.coerce.number().min(0).optional(),
  allow_offers: z.boolean().default(true),
  allow_direct_purchase: z.boolean().default(false),
  description: z.string().optional(),
  expires_at: z.string().optional(),
});

type ListingFormData = z.infer<typeof listingSchema>;

export default function CreateListingPage() {
  const locale = useLocale();
  const router = useRouter();
  const [eligibilityResult, setEligibilityResult] = useState<{
    all_passed: boolean;
    rules: { rule_number: number; rule_name: string; passed: boolean; reason?: string }[];
  } | null>(null);
  const [checkingEligibility, setCheckingEligibility] = useState(false);

  const { register, handleSubmit, watch, setValue, formState: { errors, isSubmitting } } = useForm<ListingFormData>({
    resolver: zodResolver(listingSchema),
    defaultValues: { allow_offers: true, allow_direct_purchase: false },
  });

  const selectedBatchId = watch("batch_id");

  const { data: batches, isLoading: batchesLoading } = useQuery({
    queryKey: ["batches-for-listing"],
    queryFn: () => inventoryApi.listBatches({ status: "active", page: 1, page_size: 100 }).then((r) => r.data),
  });

  const { data: selectedBatch } = useQuery({
    queryKey: ["batch", selectedBatchId],
    queryFn: () => inventoryApi.getBatch(selectedBatchId).then((r) => r.data),
    enabled: !!selectedBatchId,
  });

  const checkEligibility = async (batchId: string) => {
    if (!batchId) return;
    setCheckingEligibility(true);
    try {
      const res = await listingsApi.checkEligibility(batchId);
      setEligibilityResult(res.data);
    } catch {
      toast.error("فشل فحص الأهلية");
    } finally {
      setCheckingEligibility(false);
    }
  };

  const createListing = useMutation({
    mutationFn: (data: ListingFormData) => listingsApi.create(data),
    onSuccess: () => {
      toast.success("تم إنشاء الإعلان بنجاح");
      router.push(`/${locale}/my/listings`);
    },
    onError: () => toast.error("فشل إنشاء الإعلان"),
  });

  const onSubmit = (data: ListingFormData) => {
    if (!eligibilityResult?.all_passed) {
      toast.error("يجب اجتياز فحص الأهلية أولاً");
      return;
    }
    createListing.mutate(data);
  };

  return (
    <Shell>
      <div className="max-w-3xl space-y-6">
        <div className="flex items-center gap-3">
          <Link href={`/${locale}/my/listings`} className="text-gray-500 hover:text-gray-700">
            <ChevronRight className="h-5 w-5" />
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">إنشاء إعلان جديد</h1>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          {/* Batch Selection */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 space-y-4">
            <h2 className="font-semibold text-gray-900">اختيار الدفعة</h2>

            <div>
              <label className="text-sm text-gray-600 block mb-1">الدفعة المراد إدراجها</label>
              <select
                {...register("batch_id")}
                onChange={(e) => {
                  setValue("batch_id", e.target.value);
                  setEligibilityResult(null);
                  if (e.target.value) checkEligibility(e.target.value);
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">اختر دفعة...</option>
                {batchesLoading && <option disabled>جاري التحميل...</option>}
                {batches?.items?.map((b: {
                  id: string;
                  product_name_ar?: string;
                  product_name: string;
                  batch_number: string;
                  expiry_date: string;
                  quantity_on_hand: number;
                }) => (
                  <option key={b.id} value={b.id}>
                    {b.product_name_ar ?? b.product_name} — {b.batch_number} (
                    {b.quantity_on_hand} وحدة — ينتهي {formatDate(b.expiry_date, "ar-SA")})
                  </option>
                ))}
              </select>
              {errors.batch_id && <p className="text-red-500 text-xs mt-0.5">{errors.batch_id.message}</p>}
            </div>

            {/* Batch preview */}
            {selectedBatch && (
              <div className="bg-gray-50 rounded-lg p-4 grid grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-gray-500 text-xs">المنتج</p>
                  <p className="font-medium">{selectedBatch.product_name_ar ?? selectedBatch.product_name}</p>
                </div>
                <div>
                  <p className="text-gray-500 text-xs">الكمية المتاحة</p>
                  <p className="font-medium">{selectedBatch.quantity_on_hand} وحدة</p>
                </div>
                <div>
                  <p className="text-gray-500 text-xs">تاريخ الانتهاء</p>
                  <p className="font-medium">{formatDate(selectedBatch.expiry_date, "ar-SA")}</p>
                </div>
                <div>
                  <p className="text-gray-500 text-xs">حالة الانتهاء</p>
                  {selectedBatch.days_until_expiry !== undefined && (
                    <ExpiryBadge daysUntilExpiry={selectedBatch.days_until_expiry} />
                  )}
                </div>
              </div>
            )}

            {/* Eligibility check result */}
            {checkingEligibility && (
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>جاري فحص الأهلية...</span>
              </div>
            )}

            {eligibilityResult && (
              <div className={`rounded-lg border p-4 ${eligibilityResult.all_passed ? "border-green-200 bg-green-50" : "border-red-200 bg-red-50"}`}>
                <div className="flex items-center gap-2 mb-3">
                  {eligibilityResult.all_passed ? (
                    <CheckCircle className="h-5 w-5 text-green-500" />
                  ) : (
                    <XCircle className="h-5 w-5 text-red-500" />
                  )}
                  <span className={`font-semibold text-sm ${eligibilityResult.all_passed ? "text-green-800" : "text-red-800"}`}>
                    {eligibilityResult.all_passed ? "الدفعة مؤهلة للإدراج" : "الدفعة غير مؤهلة للإدراج"}
                  </span>
                </div>
                <ul className="space-y-1.5">
                  {eligibilityResult.rules.map((r) => (
                    <li key={r.rule_number} className="flex items-start gap-2 text-xs">
                      {r.passed ? (
                        <CheckCircle className="h-3.5 w-3.5 text-green-500 flex-shrink-0 mt-0.5" />
                      ) : (
                        <XCircle className="h-3.5 w-3.5 text-red-500 flex-shrink-0 mt-0.5" />
                      )}
                      <span className={r.passed ? "text-gray-600" : "text-red-700"}>
                        {r.rule_name}
                        {!r.passed && r.reason && (
                          <span className="block text-gray-500 mt-0.5">{r.reason}</span>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Listing Details */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 space-y-4">
            <h2 className="font-semibold text-gray-900">تفاصيل الإعلان</h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-gray-600 block mb-1">السعر المطلوب (ر.س) *</label>
                <input
                  {...register("asking_price")}
                  type="number"
                  step="0.01"
                  min="0.01"
                  dir="ltr"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                {errors.asking_price && <p className="text-red-500 text-xs mt-0.5">{errors.asking_price.message}</p>}
              </div>

              <div>
                <label className="text-sm text-gray-600 block mb-1">الكمية المعروضة *</label>
                <input
                  {...register("quantity_available")}
                  type="number"
                  min="1"
                  max={selectedBatch?.quantity_on_hand}
                  dir="ltr"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                {errors.quantity_available && <p className="text-red-500 text-xs mt-0.5">{errors.quantity_available.message}</p>}
              </div>

              <div>
                <label className="text-sm text-gray-600 block mb-1">أقل سعر مقبول (ر.س)</label>
                <input
                  {...register("minimum_offer_price")}
                  type="number"
                  step="0.01"
                  min="0"
                  dir="ltr"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="text-sm text-gray-600 block mb-1">تاريخ انتهاء الإعلان</label>
                <input
                  {...register("expires_at")}
                  type="date"
                  dir="ltr"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div>
              <label className="text-sm text-gray-600 block mb-1">وصف إضافي</label>
              <textarea
                {...register("description")}
                rows={3}
                placeholder="أضف وصفاً للإعلان..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="flex gap-6">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  {...register("allow_offers")}
                  type="checkbox"
                  className="h-4 w-4 text-blue-600 rounded"
                />
                <span className="text-sm text-gray-700">قبول العروض</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  {...register("allow_direct_purchase")}
                  type="checkbox"
                  className="h-4 w-4 text-blue-600 rounded"
                />
                <span className="text-sm text-gray-700">السماح بالشراء المباشر</span>
              </label>
            </div>
          </div>

          {/* Submit */}
          <div className="flex gap-3">
            <Link
              href={`/${locale}/my/listings`}
              className="flex-1 text-center border border-gray-300 text-gray-600 py-2.5 rounded-lg text-sm hover:bg-gray-50"
            >
              إلغاء
            </Link>
            <button
              type="submit"
              disabled={isSubmitting || !eligibilityResult?.all_passed}
              className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 rounded-lg text-sm flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
              نشر الإعلان
            </button>
          </div>

          {eligibilityResult && !eligibilityResult.all_passed && (
            <p className="text-center text-sm text-red-600">
              لا يمكن نشر الإعلان حتى تجتاز جميع شروط الأهلية
            </p>
          )}
        </form>
      </div>
    </Shell>
  );
}
