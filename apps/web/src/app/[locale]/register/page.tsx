"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslations, useLocale } from "next-intl";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { authApi } from "@/lib/api";
import { Pill, Loader2, ChevronRight, ChevronLeft, Check } from "lucide-react";

const registerSchema = z.object({
  full_name: z.string().min(2, "الاسم مطلوب"),
  email: z.string().email("البريد الإلكتروني غير صحيح"),
  phone: z.string().min(9, "رقم الهاتف غير صحيح"),
  password: z.string().min(8, "كلمة المرور يجب أن تكون 8 أحرف على الأقل"),
  org_name: z.string().min(2, "اسم الصيدلية مطلوب"),
  org_name_ar: z.string().optional(),
  commercial_registration_number: z.string().min(5, "رقم السجل التجاري مطلوب"),
  license_number: z.string().optional(),
  org_email: z.string().email("البريد الإلكتروني للمنظمة غير صحيح"),
  org_phone: z.string().min(9, "رقم الهاتف مطلوب"),
  org_city: z.string().optional(),
  org_region: z.string().optional(),
  branch_name: z.string().min(2, "اسم الفرع مطلوب"),
  branch_name_ar: z.string().optional(),
  branch_city: z.string().optional(),
  branch_phone: z.string().optional(),
});

type RegisterForm = z.infer<typeof registerSchema>;

const STEPS = [
  { id: 1, label: "معلومات المستخدم" },
  { id: 2, label: "معلومات المنظمة" },
  { id: 3, label: "معلومات الفرع" },
];

export default function RegisterPage() {
  const t = useTranslations("auth");
  const locale = useLocale();
  const router = useRouter();
  const [step, setStep] = useState(1);

  const {
    register,
    handleSubmit,
    trigger,
    formState: { errors, isSubmitting },
  } = useForm<RegisterForm>({ resolver: zodResolver(registerSchema) });

  const step1Fields: (keyof RegisterForm)[] = ["full_name", "email", "phone", "password"];
  const step2Fields: (keyof RegisterForm)[] = ["org_name", "commercial_registration_number", "org_email", "org_phone"];
  const step3Fields: (keyof RegisterForm)[] = ["branch_name"];

  const nextStep = async () => {
    const fields = step === 1 ? step1Fields : step === 2 ? step2Fields : step3Fields;
    const valid = await trigger(fields);
    if (valid) setStep((s) => Math.min(s + 1, 3));
  };

  const onSubmit = async (data: RegisterForm) => {
    try {
      await authApi.register(data);
      router.push(`/${locale}/pending-review`);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(typeof msg === "string" ? msg : "فشل التسجيل. حاول مرة أخرى.");
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4" dir="rtl">
      <div className="w-full max-w-lg bg-white rounded-2xl shadow-xl p-8">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-6">
          <div className="h-10 w-10 bg-blue-600 rounded-xl flex items-center justify-center">
            <Pill className="h-5 w-5 text-white" />
          </div>
          <p className="text-lg font-bold text-gray-900">سوق الصيدليات</p>
        </div>

        {/* Step indicators */}
        <div className="flex items-center justify-center gap-2 mb-8">
          {STEPS.map((s) => (
            <div key={s.id} className="flex items-center gap-2">
              <div
                className={`h-8 w-8 rounded-full flex items-center justify-center text-sm font-bold ${
                  step > s.id
                    ? "bg-green-500 text-white"
                    : step === s.id
                    ? "bg-blue-600 text-white"
                    : "bg-gray-200 text-gray-500"
                }`}
              >
                {step > s.id ? <Check className="h-4 w-4" /> : s.id}
              </div>
              {s.id < 3 && <div className={`h-0.5 w-8 ${step > s.id ? "bg-green-500" : "bg-gray-200"}`} />}
            </div>
          ))}
        </div>

        <h2 className="text-lg font-bold text-gray-800 mb-4 text-center">
          {STEPS[step - 1].label}
        </h2>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {/* Step 1 — User */}
          {step === 1 && (
            <>
              <Field label="الاسم الكامل" error={errors.full_name?.message}>
                <input {...register("full_name")} placeholder="أحمد الرشيدي" className={inputCls} />
              </Field>
              <Field label="البريد الإلكتروني" error={errors.email?.message}>
                <input {...register("email")} type="email" placeholder="example@pharmacy.sa" className={inputCls} dir="ltr" />
              </Field>
              <Field label="رقم الهاتف" error={errors.phone?.message}>
                <input {...register("phone")} placeholder="+966500000000" className={inputCls} dir="ltr" />
              </Field>
              <Field label="كلمة المرور" error={errors.password?.message}>
                <input {...register("password")} type="password" placeholder="8 أحرف على الأقل" className={inputCls} dir="ltr" />
              </Field>
            </>
          )}

          {/* Step 2 — Organization */}
          {step === 2 && (
            <>
              <Field label="اسم الصيدلية" error={errors.org_name?.message}>
                <input {...register("org_name")} placeholder="صيدلية الشفاء" className={inputCls} />
              </Field>
              <Field label="اسم الصيدلية (عربي)" error={errors.org_name_ar?.message}>
                <input {...register("org_name_ar")} placeholder="صيدلية الشفاء" className={inputCls} />
              </Field>
              <Field label="رقم السجل التجاري" error={errors.commercial_registration_number?.message}>
                <input {...register("commercial_registration_number")} placeholder="CR-XXXXXXXXXX" className={inputCls} dir="ltr" />
              </Field>
              <Field label="رقم الترخيص" error={errors.license_number?.message}>
                <input {...register("license_number")} placeholder="LIC-XXXXXXXXX (اختياري)" className={inputCls} dir="ltr" />
              </Field>
              <Field label="البريد الإلكتروني للمنظمة" error={errors.org_email?.message}>
                <input {...register("org_email")} type="email" className={inputCls} dir="ltr" />
              </Field>
              <Field label="رقم هاتف المنظمة" error={errors.org_phone?.message}>
                <input {...register("org_phone")} placeholder="+966112345678" className={inputCls} dir="ltr" />
              </Field>
            </>
          )}

          {/* Step 3 — Branch */}
          {step === 3 && (
            <>
              <Field label="اسم الفرع" error={errors.branch_name?.message}>
                <input {...register("branch_name")} placeholder="الفرع الرئيسي" className={inputCls} />
              </Field>
              <Field label="اسم الفرع (عربي)" error={errors.branch_name_ar?.message}>
                <input {...register("branch_name_ar")} placeholder="الفرع الرئيسي" className={inputCls} />
              </Field>
              <Field label="المدينة" error={errors.branch_city?.message}>
                <input {...register("branch_city")} placeholder="الرياض" className={inputCls} />
              </Field>
              <Field label="رقم هاتف الفرع" error={errors.branch_phone?.message}>
                <input {...register("branch_phone")} placeholder="+966112345678" className={inputCls} dir="ltr" />
              </Field>
            </>
          )}

          {/* Navigation */}
          <div className="flex gap-3 pt-2">
            {step > 1 && (
              <button
                type="button"
                onClick={() => setStep((s) => s - 1)}
                className="flex-1 border border-gray-300 text-gray-700 font-medium py-2.5 rounded-lg flex items-center justify-center gap-1 hover:bg-gray-50"
              >
                <ChevronLeft className="h-4 w-4" />
                السابق
              </button>
            )}
            {step < 3 ? (
              <button
                type="button"
                onClick={nextStep}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 rounded-lg flex items-center justify-center gap-1"
              >
                التالي
                <ChevronRight className="h-4 w-4" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={isSubmitting}
                className="flex-1 bg-green-600 hover:bg-green-700 text-white font-semibold py-2.5 rounded-lg flex items-center justify-center gap-2 disabled:opacity-60"
              >
                {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                إنشاء الحساب
              </button>
            )}
          </div>
        </form>

        <p className="text-center text-sm text-gray-600 mt-4">
          لديك حساب بالفعل؟{" "}
          <Link href={`/${locale}/login`} className="text-blue-600 font-medium hover:underline">
            تسجيل الدخول
          </Link>
        </p>
      </div>
    </div>
  );
}

const inputCls =
  "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      {children}
      {error && <p className="text-red-500 text-xs mt-1">{error}</p>}
    </div>
  );
}
