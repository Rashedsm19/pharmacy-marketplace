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
import { formatDate } from "@/lib/utils";
import { ExpiryBadge } from "@/components/ui/expiry-badge";
import { CheckCircle, XCircle, Loader2, ArrowRight, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { SectionCard } from "@/components/ui/section-card";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";

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

const inputCls =
  "w-full h-10 px-3 bg-[#fbf7f0]/80 ring-1 ring-inset ring-[#d8c8b3] rounded-full text-sm placeholder:text-[#9a8b77] focus:outline-none focus:bg-white focus:ring-2 focus:ring-brand-500 transition-colors";

export default function CreateListingPage() {
  const locale = useLocale();
  const router = useRouter();
  const [eligibilityResult, setEligibilityResult] = useState<{
    all_passed: boolean;
    rules: { rule_number: number; rule_name: string; passed: boolean; reason?: string }[];
  } | null>(null);
  const [checkingEligibility, setCheckingEligibility] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<ListingFormData>({
    resolver: zodResolver(listingSchema),
    defaultValues: { allow_offers: true, allow_direct_purchase: false },
  });

  const selectedBatchId = watch("batch_id");

  const { data: batches, isLoading: batchesLoading } = useQuery({
    queryKey: ["batches-for-listing"],
    queryFn: () =>
      inventoryApi
        .listBatches({ status: "active", page: 1, page_size: 100 })
        .then((r) => r.data),
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
      toast.success("تم نشر العرض بنجاح");
      router.push(`/${locale}/my/listings`);
    },
    onError: () => toast.error("فشل نشر العرض"),
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
      <div className="space-y-6">
        <PageHeader
          title="نشر عرض جديد"
          subtitle="اختر دفعة مؤهلة وحدد تفاصيل العرض، وسيتم فحص الأهلية تلقائياً قبل النشر"
          back={
            <Link
              href={`/${locale}/my/listings`}
              className="inline-flex items-center gap-1 text-xs text-[#6d746d] hover:text-[#1f2a24]"
            >
              <ArrowRight className="h-3.5 w-3.5" />
              العودة للعروض المنشورة
            </Link>
          }
        />

        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            {/* LEFT — main form */}
            <div className="lg:col-span-2 space-y-5">
              <SectionCard title="اختيار الدفعة">
                <div className="space-y-4">
                  <div>
                    <label className="text-xs font-medium text-[#4d554e] block mb-1.5">
                      الدفعة المراد عرضها <span className="text-rose-500">*</span>
                    </label>
                    <select
                      {...register("batch_id")}
                      onChange={(e) => {
                        setValue("batch_id", e.target.value);
                        setEligibilityResult(null);
                        if (e.target.value) checkEligibility(e.target.value);
                      }}
                      className={inputCls}
                    >
                      <option value="">اختر دفعة...</option>
                      {batchesLoading && <option disabled>جاري التحميل...</option>}
                      {batches?.items?.map(
                        (b: {
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
                        )
                      )}
                    </select>
                    {errors.batch_id && (
                      <p className="text-rose-600 text-xs mt-1">{errors.batch_id.message}</p>
                    )}
                  </div>

                  {selectedBatch && (
                    <div className="bg-[#f7efe3] ring-1 ring-[#eadfcc] rounded-2xl p-4 grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
                      <div>
                        <p className="text-[11px] uppercase tracking-normal text-[#7d6d58] mb-0.5">المنتج</p>
                        <p className="font-semibold text-[#1f2a24]">
                          {selectedBatch.product_name_ar ?? selectedBatch.product_name}
                        </p>
                      </div>
                      <div>
                        <p className="text-[11px] uppercase tracking-normal text-[#7d6d58] mb-0.5">الكمية المتاحة</p>
                        <p className="font-semibold text-[#1f2a24] tabular-nums">
                          {selectedBatch.quantity_on_hand} وحدة
                        </p>
                      </div>
                      <div>
                        <p className="text-[11px] uppercase tracking-normal text-[#7d6d58] mb-0.5">تاريخ الانتهاء</p>
                        <p className="font-semibold text-[#1f2a24] tabular-nums">
                          {formatDate(selectedBatch.expiry_date, "ar-SA")}
                        </p>
                      </div>
                      <div>
                        <p className="text-[11px] uppercase tracking-normal text-[#7d6d58] mb-0.5">حالة الانتهاء</p>
                        {selectedBatch.days_until_expiry !== undefined && (
                          <ExpiryBadge daysUntilExpiry={selectedBatch.days_until_expiry} />
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </SectionCard>

              <SectionCard title="تفاصيل العرض">
                <div className="space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs font-medium text-[#4d554e] block mb-1.5">
                        السعر المطلوب (ر.س) <span className="text-rose-500">*</span>
                      </label>
                      <input
                        {...register("asking_price")}
                        type="number"
                        step="0.01"
                        min="0.01"
                        dir="ltr"
                        className={inputCls}
                      />
                      {errors.asking_price && (
                        <p className="text-rose-600 text-xs mt-1">{errors.asking_price.message}</p>
                      )}
                    </div>
                    <div>
                      <label className="text-xs font-medium text-[#4d554e] block mb-1.5">
                        الكمية المعروضة <span className="text-rose-500">*</span>
                      </label>
                      <input
                        {...register("quantity_available")}
                        type="number"
                        min="1"
                        max={selectedBatch?.quantity_on_hand}
                        dir="ltr"
                        className={inputCls}
                      />
                      {errors.quantity_available && (
                        <p className="text-rose-600 text-xs mt-1">
                          {errors.quantity_available.message}
                        </p>
                      )}
                    </div>
                    <div>
                      <label className="text-xs font-medium text-[#4d554e] block mb-1.5">
                        أقل سعر مقبول (ر.س)
                      </label>
                      <input
                        {...register("minimum_offer_price")}
                        type="number"
                        step="0.01"
                        min="0"
                        dir="ltr"
                        className={inputCls}
                      />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-[#4d554e] block mb-1.5">
                        تاريخ انتهاء العرض
                      </label>
                      <input
                        {...register("expires_at")}
                        type="date"
                        dir="ltr"
                        className={inputCls}
                      />
                    </div>
                  </div>

                  <div>
                    <label className="text-xs font-medium text-[#4d554e] block mb-1.5">
                      وصف إضافي
                    </label>
                    <textarea
                      {...register("description")}
                      rows={3}
                      placeholder="أضف ملاحظات تشغيلية عن العرض..."
                      className="w-full px-3 py-2 bg-[#fbf7f0]/80 ring-1 ring-inset ring-[#d8c8b3] rounded-2xl text-sm placeholder:text-[#9a8b77] focus:outline-none focus:bg-white focus:ring-2 focus:ring-brand-500 transition-colors"
                    />
                  </div>

                  <div className="flex flex-wrap gap-x-6 gap-y-3">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        {...register("allow_offers")}
                        type="checkbox"
                        className="h-4 w-4 rounded border-[#cdbda8] text-brand-600 focus:ring-brand-500"
                      />
                      <span className="text-sm text-[#4d554e]">قبول طلبات التفاوض</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        {...register("allow_direct_purchase")}
                        type="checkbox"
                        className="h-4 w-4 rounded border-[#cdbda8] text-brand-600 focus:ring-brand-500"
                      />
                      <span className="text-sm text-[#4d554e]">السماح بالشراء المباشر</span>
                    </label>
                  </div>
                </div>
              </SectionCard>

              {/* Submit */}
              <div className="flex flex-col sm:flex-row gap-3">
                <Link
                  href={`/${locale}/my/listings`}
                  className="flex-1 inline-flex items-center justify-center h-11 rounded-full ring-1 ring-inset ring-[#cdbda8] bg-white/80 text-sm font-medium text-[#4d554e] hover:bg-[#f4eadf]"
                >
                  إلغاء
                </Link>
                <Button
                  type="submit"
                  variant="primary"
                  size="lg"
                  className="flex-1"
                  loading={isSubmitting}
                  disabled={!eligibilityResult?.all_passed}
                >
                  نشر العرض
                </Button>
              </div>
            </div>

            {/* RIGHT — sticky eligibility panel */}
            <div className="lg:col-span-1">
              <div className="lg:sticky lg:top-[88px]">
                <SectionCard
                  title={
                    <span className="inline-flex items-center gap-2">
                      <ShieldCheck className="h-4 w-4 text-brand-600" />
                      فحص الأهلية
                    </span>
                  }
                  subtitle="10 قواعد امتثال يجب اجتيازها"
                >
                  {!eligibilityResult && !checkingEligibility && (
                    <div className="text-center py-8 text-sm text-[#6d746d]">
                      اختر دفعة لبدء فحص الأهلية
                    </div>
                  )}

                  {checkingEligibility && (
                    <div className="flex items-center justify-center gap-2 py-6 text-sm text-[#6d746d]">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>جاري الفحص...</span>
                    </div>
                  )}

                  {eligibilityResult && (
                    <>
                      <div
                        className={`rounded-xl p-3 mb-3 flex items-center gap-2.5 ring-1 ${
                          eligibilityResult.all_passed
                            ? "bg-emerald-50 ring-emerald-200 text-emerald-800"
                            : "bg-rose-50 ring-rose-200 text-rose-800"
                        }`}
                      >
                        {eligibilityResult.all_passed ? (
                          <CheckCircle className="h-5 w-5 text-emerald-600 flex-shrink-0" />
                        ) : (
                          <XCircle className="h-5 w-5 text-rose-600 flex-shrink-0" />
                        )}
                        <span className="font-semibold text-sm">
                          {eligibilityResult.all_passed
                            ? "الدفعة مؤهلة للإدراج"
                            : "الدفعة غير مؤهلة"}
                        </span>
                      </div>
                      <ul className="space-y-2.5">
                        {eligibilityResult.rules.map((r) => (
                          <li key={r.rule_number} className="flex items-start gap-2.5">
                            {r.passed ? (
                              <div className="h-5 w-5 rounded-full bg-emerald-50 ring-1 ring-emerald-200 flex items-center justify-center flex-shrink-0 mt-0.5">
                                <CheckCircle className="h-3 w-3 text-emerald-600" />
                              </div>
                            ) : (
                              <div className="h-5 w-5 rounded-full bg-rose-50 ring-1 ring-rose-200 flex items-center justify-center flex-shrink-0 mt-0.5">
                                <XCircle className="h-3 w-3 text-rose-600" />
                              </div>
                            )}
                            <div className="min-w-0 text-xs">
                              <p
                                className={
                                  r.passed
                                    ? "text-[#4d554e] font-medium"
                                    : "text-rose-700 font-semibold"
                                }
                              >
                                {r.rule_name}
                              </p>
                              {!r.passed && r.reason && (
                                <p className="text-[#6d746d] mt-0.5">{r.reason}</p>
                              )}
                            </div>
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </SectionCard>
              </div>
            </div>
          </div>
        </form>
      </div>
    </Shell>
  );
}
