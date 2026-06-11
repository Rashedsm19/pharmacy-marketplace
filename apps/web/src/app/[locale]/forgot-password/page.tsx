"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useLocale } from "next-intl";
import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { authApi } from "@/lib/api";
import { Loader2, CheckCircle } from "lucide-react";
import BrandLogo from "@/components/brand-logo";

const schema = z.object({
  email: z.string().email("البريد الإلكتروني غير صحيح"),
});

type ForgotPasswordForm = z.infer<typeof schema>;

export default function ForgotPasswordPage() {
  const locale = useLocale();
  const [sent, setSent] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotPasswordForm>({ resolver: zodResolver(schema) });

  const onSubmit = async ({ email }: ForgotPasswordForm) => {
    try {
      await authApi.forgotPassword(email);
      setSent(true);
    } catch {
      toast.error("حدث خطأ. حاول مرة أخرى.");
    }
  };

  return (
    <div className="min-h-screen bg-app-shell flex items-center justify-center overflow-x-hidden p-4" dir="rtl">
      <div className="w-[calc(100vw-2rem)] max-w-md min-w-0 bg-[#fffdf9]/95 rounded-3xl shadow-lift ring-1 ring-[#e2d4bf] p-8">
        <div className="flex items-center justify-center gap-3 mb-8">
          <BrandLogo size="md" />
        </div>

        {!sent ? (
          <>
            <h1 className="text-2xl font-semibold text-[#1f2a24] text-center mb-2">استعادة الوصول</h1>
            <p className="text-[#6d746d] text-sm text-center mb-6 leading-relaxed">
              أدخل البريد المعتمد لدى المنشأة لإرسال رابط إعادة تعيين آمن.
            </p>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-[#4d554e] mb-1">
                  البريد الإلكتروني
                </label>
                <input
                  {...register("email")}
                  type="email"
                  className="w-full px-4 py-2.5 bg-[#fbf7f0]/80 border border-[#d8c8b3] rounded-full text-sm placeholder:text-[#9a8b77] focus:outline-none focus:bg-white focus:ring-2 focus:ring-brand-500"
                  placeholder="example@pharmacy.sa"
                  dir="ltr"
                />
                {errors.email && (
                  <p className="text-red-500 text-xs mt-1">{errors.email.message}</p>
                )}
              </div>
              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full bg-[#1f2a24] hover:bg-brand-800 text-[#fbf7f0] font-semibold py-2.5 rounded-full flex items-center justify-center gap-2 disabled:opacity-60"
              >
                {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                إرسال الرابط
              </button>
            </form>
          </>
        ) : (
          <div className="text-center">
            <CheckCircle className="h-16 w-16 text-brand-600 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-[#1f2a24] mb-2">تم إرسال الطلب</h2>
            <p className="text-[#6d746d] mb-6">
              إذا كان البريد الإلكتروني مسجلاً، ستصلك رسالة تحتوي على رابط إعادة التعيين.
            </p>
          </div>
        )}

        <p className="text-center text-sm text-[#6d746d] mt-4">
          <Link href={`/${locale}/login`} className="text-brand-700 hover:underline">
            العودة لتسجيل الدخول
          </Link>
        </p>
      </div>
    </div>
  );
}
