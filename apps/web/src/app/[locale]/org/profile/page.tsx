"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { useEffect } from "react";
import Shell from "@/components/layout/shell";
import { Badge } from "@/components/ui/badge";
import { organizationsApi } from "@/lib/api";
import { OrgDocumentsUpload } from "@/components/org-documents";
import { Loader2, Building2, CheckCircle, AlertCircle, Clock, FileText } from "lucide-react";

const profileSchema = z.object({
  name: z.string().min(2, "الاسم مطلوب"),
  name_ar: z.string().min(2, "الاسم العربي مطلوب"),
  phone: z.string().optional(),
  email: z.string().email("بريد إلكتروني غير صحيح").optional().or(z.literal("")),
  address: z.string().optional(),
  website: z.string().url("رابط غير صحيح").optional().or(z.literal("")),
  // Regulatory identity — mirrors the server-side rules so the user is told
  // before the request is sent.
  vat_number: z
    .string()
    .regex(/^3\d{13}3$/, "الرقم الضريبي: ١٥ رقما يبدأ وينتهي ب٣")
    .optional()
    .or(z.literal("")),
  gln: z
    .string()
    .regex(/^\d{13}$/, "رقم الموقع العالمي GLN: ١٣ رقما")
    .optional()
    .or(z.literal("")),
  license_expires_at: z.string().optional().or(z.literal("")),
});

type ProfileFormData = z.infer<typeof profileSchema>;

const STATUS_CONFIG: Record<string, { label: string; variant: "success" | "warning" | "danger" | "default"; icon: React.ReactNode }> = {
  approved: { label: "معتمد", variant: "success", icon: <CheckCircle className="h-4 w-4" /> },
  pending: { label: "قيد المراجعة", variant: "warning", icon: <Clock className="h-4 w-4" /> },
  suspended: { label: "موقوف", variant: "danger", icon: <AlertCircle className="h-4 w-4" /> },
  rejected: { label: "مرفوض", variant: "danger", icon: <AlertCircle className="h-4 w-4" /> },
};

export default function OrgProfilePage() {
  const qc = useQueryClient();

  const { data: org, isLoading } = useQuery({
    queryKey: ["org-profile"],
    queryFn: () => organizationsApi.getMyOrg().then((r) => r.data),
  });

  const { register, handleSubmit, reset, formState: { errors, isSubmitting, isDirty } } = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
  });

  useEffect(() => {
    if (org) {
      reset({
        name: org.name ?? "",
        name_ar: org.name_ar ?? "",
        phone: org.phone ?? "",
        email: org.email ?? "",
        address: org.address ?? "",
        website: org.website ?? "",
        vat_number: org.vat_number ?? "",
        gln: org.gln ?? "",
        license_expires_at: org.license_expires_at ?? "",
      });
    }
  }, [org, reset]);

  const updateOrg = useMutation({
    // Blank optional inputs are sent as "", which the API would reject on
    // format; drop them so "cleared" and "untouched" both mean null.
    mutationFn: (data: ProfileFormData) =>
      organizationsApi.updateMyOrg(
        Object.fromEntries(Object.entries(data).filter(([, v]) => v !== ""))
      ),
    onSuccess: () => {
      toast.success("تم حفظ التغييرات");
      qc.invalidateQueries({ queryKey: ["org-profile"] });
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      const msg = Array.isArray(detail) ? detail[0]?.msg : detail;
      toast.error(typeof msg === "string" ? msg : "فشل حفظ التغييرات");
    },
  });

  if (isLoading) {
    return (
      <Shell>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-8 w-8 animate-spin text-brand-600" />
        </div>
      </Shell>
    );
  }

  const status = org?.status ?? "pending";
  const statusCfg = STATUS_CONFIG[status] ?? { label: status, variant: "default", icon: null };

  return (
    <Shell>
      <div className="max-w-3xl space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">ملف المنشأة</h1>
          <div className="flex items-center gap-1.5">
            {statusCfg.icon}
            <Badge variant={statusCfg.variant}>{statusCfg.label}</Badge>
          </div>
        </div>

        {/* Status banner */}
        {status === "pending" && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 flex items-start gap-3">
            <Clock className="h-5 w-5 text-yellow-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-yellow-800">طلبك قيد المراجعة</p>
              <p className="text-sm text-yellow-700 mt-0.5">
                سيتم مراجعة طلبك من قبل فريقنا وإخطارك فور الانتهاء.
              </p>
            </div>
          </div>
        )}

        {status === "suspended" && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-red-800">الحساب موقوف</p>
              <p className="text-sm text-red-700 mt-0.5">تم إيقاف حسابك. تواصل مع الدعم الفني لمزيد من المعلومات.</p>
            </div>
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: "الفروع", value: org?.branch_count ?? 0 },
            { label: "العروض النشطة", value: org?.active_listings_count ?? 0 },
            { label: "المعاملات المكتملة", value: org?.completed_transactions_count ?? 0 },
            { label: "الرقم الضريبي", value: org?.vat_number ?? "—" },
          ].map((item) => (
            <div key={item.label} className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
              <p className="text-gray-500 text-xs">{item.label}</p>
              <p className="font-bold text-gray-900 text-lg mt-1">{item.value}</p>
            </div>
          ))}
        </div>

        {/* Compliance documents — only meaningful for a user who belongs to an org */}
        {org?.id && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <div className="flex items-center gap-2 mb-4">
              <FileText className="h-5 w-5 text-brand-600" />
              <h2 className="font-semibold text-gray-900">مستندات الاعتماد</h2>
            </div>
            <OrgDocumentsUpload
              orgId={org.id}
              crDoc={org.cr_doc_url}
              licenseDoc={org.license_doc_url}
              onChanged={() => qc.invalidateQueries({ queryKey: ["org-profile"] })}
            />
          </div>
        )}

        {/* Profile form */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <div className="flex items-center gap-2 mb-6">
            <Building2 className="h-5 w-5 text-brand-600" />
            <h2 className="font-semibold text-gray-900">معلومات المنشأة</h2>
          </div>

          <form onSubmit={handleSubmit((d) => updateOrg.mutate(d))} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-gray-600 block mb-1">اسم المنشأة (عربي) *</label>
                <input
                  {...register("name_ar")}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
                {errors.name_ar && <p className="text-red-500 text-xs mt-0.5">{errors.name_ar.message}</p>}
              </div>
              <div>
                <label className="text-sm text-gray-600 block mb-1">اسم المنشأة (إنجليزي)</label>
                <input
                  {...register("name")}
                  dir="ltr"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
                {errors.name && <p className="text-red-500 text-xs mt-0.5">{errors.name.message}</p>}
              </div>
              <div>
                <label className="text-sm text-gray-600 block mb-1">رقم الهاتف</label>
                <input
                  {...register("phone")}
                  type="tel"
                  dir="ltr"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="text-sm text-gray-600 block mb-1">البريد الإلكتروني</label>
                <input
                  {...register("email")}
                  type="email"
                  dir="ltr"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
                {errors.email && <p className="text-red-500 text-xs mt-0.5">{errors.email.message}</p>}
              </div>
            </div>

            <div>
              <label className="text-sm text-gray-600 block mb-1">العنوان</label>
              <input
                {...register("address")}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>

            <div>
              <label className="text-sm text-gray-600 block mb-1">الموقع الإلكتروني</label>
              <input
                {...register("website")}
                type="url"
                dir="ltr"
                placeholder="https://"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              {errors.website && <p className="text-red-500 text-xs mt-0.5">{errors.website.message}</p>}
            </div>

            {/* Regulatory identity — needed before invoices or traceability
                reports can be filed on this organization's behalf. */}
            <div className="border-t pt-4 space-y-4">
              <p className="text-xs text-gray-500">
                هذه البيانات مطلوبة لإصدار الفواتير الضريبية والإبلاغ عن حركة الدواء.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-gray-600 block mb-1">الرقم الضريبي</label>
                  <input
                    {...register("vat_number")}
                    dir="ltr"
                    inputMode="numeric"
                    placeholder="300000000000003"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                  {errors.vat_number && (
                    <p className="text-red-500 text-xs mt-0.5">{errors.vat_number.message}</p>
                  )}
                </div>
                <div>
                  <label className="text-sm text-gray-600 block mb-1">
                    رقم الموقع العالمي (GLN)
                  </label>
                  <input
                    {...register("gln")}
                    dir="ltr"
                    inputMode="numeric"
                    placeholder="6287000000009"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                  {errors.gln && <p className="text-red-500 text-xs mt-0.5">{errors.gln.message}</p>}
                </div>
                <div>
                  <label className="text-sm text-gray-600 block mb-1">
                    تاريخ انتهاء الترخيص
                  </label>
                  <input
                    {...register("license_expires_at")}
                    type="date"
                    dir="ltr"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>
              </div>
            </div>

            {/* Read-only compliance fields */}
            <div className="border-t pt-4 grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-gray-400 text-xs">ترخيص الصيدلية</p>
                <p className="font-medium text-gray-900 flex items-center gap-1 mt-0.5">
                  {org?.is_licensed ? (
                    <><CheckCircle className="h-3.5 w-3.5 text-green-500" /> مرخص</>
                  ) : (
                    <><AlertCircle className="h-3.5 w-3.5 text-red-500" /> غير مرخص</>
                  )}
                </p>
              </div>
              <div>
                <p className="text-gray-400 text-xs">رقم الترخيص</p>
                <p className="font-medium text-gray-900" dir="ltr">{org?.license_number ?? "—"}</p>
              </div>
              <div>
                <p className="text-gray-400 text-xs">تاريخ انتهاء الترخيص</p>
                <p className="font-medium text-gray-900">
                  {org?.license_expiry_date
                    ? new Date(org.license_expiry_date).toLocaleDateString("ar-SA")
                    : "—"}
                </p>
              </div>
              <div>
                <p className="text-gray-400 text-xs">الرقم الضريبي</p>
                <p className="font-medium text-gray-900" dir="ltr">{org?.tax_number ?? "—"}</p>
              </div>
            </div>

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={isSubmitting || !isDirty}
                className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-6 py-2.5 rounded-lg text-sm font-medium disabled:opacity-60"
              >
                {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                حفظ التغييرات
              </button>
            </div>
          </form>
        </div>
      </div>
    </Shell>
  );
}
