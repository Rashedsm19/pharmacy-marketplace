"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocale } from "next-intl";
import { useParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import Shell from "@/components/layout/shell";
import { ExpiryBadge } from "@/components/ui/expiry-badge";
import { Badge } from "@/components/ui/badge";
import { listingsApi, offersApi } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import { ChevronRight, CheckCircle, XCircle, Loader2 } from "lucide-react";
import Link from "next/link";

const offerSchema = z.object({
  offered_price: z.coerce.number().min(0.01, "السعر مطلوب"),
  quantity: z.coerce.number().int().min(1, "الكمية مطلوبة"),
  message: z.string().optional(),
});

type OfferForm = z.infer<typeof offerSchema>;

export default function ListingDetailPage() {
  const locale = useLocale();
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [showOfferForm, setShowOfferForm] = useState(false);

  const { data: listing, isLoading } = useQuery({
    queryKey: ["listing", id],
    queryFn: () => listingsApi.get(id).then((r) => r.data),
  });

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<OfferForm>({
    resolver: zodResolver(offerSchema),
  });

  const submitOffer = useMutation({
    mutationFn: (data: { offered_price: number; quantity: number; message?: string }) =>
      offersApi.submit({ listing_id: id, ...data }),
    onSuccess: () => {
      toast.success("تم تقديم العرض بنجاح");
      setShowOfferForm(false);
      qc.invalidateQueries({ queryKey: ["listing", id] });
    },
    onError: () => toast.error("فشل تقديم العرض"),
  });

  if (isLoading) {
    return (
      <Shell>
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin h-8 w-8 border-4 border-blue-600 border-t-transparent rounded-full" />
        </div>
      </Shell>
    );
  }

  if (!listing) return <Shell><p className="text-gray-500">لم يتم العثور على الإعلان</p></Shell>;

  const eligibility = listing.eligibility_result_detail;

  return (
    <Shell>
      <div className="max-w-4xl space-y-6">
        <div className="flex items-center gap-3">
          <Link href={`/${locale}/marketplace`} className="text-gray-500 hover:text-gray-700">
            <ChevronRight className="h-5 w-5" />
          </Link>
          <h1 className="text-2xl font-bold text-gray-900 flex-1 line-clamp-1">
            {listing.title_ar ?? listing.title}
          </h1>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Main details */}
          <div className="xl:col-span-2 space-y-4">
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <p className="text-3xl font-bold text-blue-600">
                    {formatCurrency(listing.asking_price)}
                  </p>
                  <p className="text-sm text-gray-500">السعر المطلوب</p>
                </div>
                {listing.days_until_expiry !== undefined && (
                  <ExpiryBadge daysUntilExpiry={listing.days_until_expiry} />
                )}
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm">
                <Detail label="المنتج" value={listing.product_name_ar ?? listing.product_name} />
                <Detail label="الدفعة" value={listing.batch_number} />
                <Detail label="الكمية المتاحة" value={`${listing.quantity_available} وحدة`} />
                <Detail
                  label="تاريخ الانتهاء"
                  value={listing.expiry_date ? formatDate(listing.expiry_date, "ar-SA") : "—"}
                />
                <Detail label="البائع" value={listing.seller_org_name} />
                <Detail label="الفرع" value={listing.seller_branch_name} />
                {listing.minimum_offer_price && (
                  <Detail
                    label="أقل سعر مقبول"
                    value={formatCurrency(listing.minimum_offer_price)}
                  />
                )}
              </div>

              {listing.description && (
                <p className="mt-4 text-sm text-gray-600 border-t pt-4">{listing.description}</p>
              )}
            </div>

            {/* Eligibility result */}
            {eligibility && (
              <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
                <div className="flex items-center gap-2 mb-4">
                  {eligibility.all_passed ? (
                    <CheckCircle className="h-5 w-5 text-green-500" />
                  ) : (
                    <XCircle className="h-5 w-5 text-red-500" />
                  )}
                  <h3 className="font-semibold text-gray-900">نتيجة فحص الأهلية</h3>
                </div>
                <ul className="space-y-1.5">
                  {eligibility.rules?.map((r: { rule_number: number; rule_name: string; passed: boolean; reason?: string }) => (
                    <li key={r.rule_number} className="flex items-start gap-2 text-sm">
                      {r.passed ? (
                        <CheckCircle className="h-4 w-4 text-green-500 flex-shrink-0 mt-0.5" />
                      ) : (
                        <XCircle className="h-4 w-4 text-red-500 flex-shrink-0 mt-0.5" />
                      )}
                      <span className={r.passed ? "text-gray-700" : "text-red-600"}>
                        {r.rule_name}
                        {!r.passed && r.reason && <span className="text-xs block text-gray-500">{r.reason}</span>}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Action panel */}
          <div className="space-y-4">
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h3 className="font-semibold text-gray-900 mb-4">الإجراءات</h3>

              {listing.allow_offers && (
                <>
                  {!showOfferForm ? (
                    <button
                      onClick={() => setShowOfferForm(true)}
                      className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 rounded-lg text-sm"
                    >
                      تقديم عرض
                    </button>
                  ) : (
                    <form
                      onSubmit={handleSubmit((d) => submitOffer.mutate(d))}
                      className="space-y-3"
                    >
                      <div>
                        <label className="text-xs text-gray-600">سعر العرض (ر.س)</label>
                        <input
                          {...register("offered_price")}
                          type="number"
                          step="0.01"
                          className="w-full mt-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                          dir="ltr"
                        />
                        {errors.offered_price && (
                          <p className="text-red-500 text-xs mt-0.5">{errors.offered_price.message}</p>
                        )}
                      </div>
                      <div>
                        <label className="text-xs text-gray-600">الكمية</label>
                        <input
                          {...register("quantity")}
                          type="number"
                          min={1}
                          max={listing.quantity_available}
                          className="w-full mt-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                          dir="ltr"
                        />
                        {errors.quantity && (
                          <p className="text-red-500 text-xs mt-0.5">{errors.quantity.message}</p>
                        )}
                      </div>
                      <div>
                        <label className="text-xs text-gray-600">رسالة (اختياري)</label>
                        <textarea
                          {...register("message")}
                          rows={2}
                          className="w-full mt-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => setShowOfferForm(false)}
                          className="flex-1 border border-gray-300 text-gray-600 py-2 rounded-lg text-sm hover:bg-gray-50"
                        >
                          إلغاء
                        </button>
                        <button
                          type="submit"
                          disabled={isSubmitting}
                          className="flex-1 bg-blue-600 text-white py-2 rounded-lg text-sm font-medium flex items-center justify-center gap-1 disabled:opacity-60"
                        >
                          {isSubmitting && <Loader2 className="h-3 w-3 animate-spin" />}
                          إرسال
                        </button>
                      </div>
                    </form>
                  )}
                </>
              )}

              <div className="mt-3 pt-3 border-t border-gray-100 space-y-1.5">
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span>عدد المشاهدات</span>
                  <span>{listing.view_count ?? 0}</span>
                </div>
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span>الحالة</span>
                  <Badge variant={listing.status === "active" ? "success" : "default"}>
                    {listing.status}
                  </Badge>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
}

function Detail({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div>
      <p className="text-gray-500 text-xs mb-0.5">{label}</p>
      <p className="font-medium text-gray-900 text-sm">{value ?? "—"}</p>
    </div>
  );
}
