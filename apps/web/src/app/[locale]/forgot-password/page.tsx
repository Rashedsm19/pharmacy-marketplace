"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useLocale } from "next-intl";
import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { authApi } from "@/lib/api";
import { Pill, Loader2, CheckCircle } from "lucide-react";

const schema = z.object({
  email: z.string().email("البريد الإلكتروني غير صحيح"),
});

export default function ForgotPasswordPage() {
  const locale = useLocale();
  const [sent, setSent] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(schema) });

  const onSubmit = async ({ email }: { email: string }) => {
    try {
      await authApi.forgotPassword(email);
      setSent(true);
    } catch {
      toast.error("حدث خطأ. حاول مرة أخرى.");
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4" dir="rtl">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-8">
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="h-10 w-10 bg-blue-600 rounded-xl flex items-center justify-center">
            <Pill className="h-5 w-5 text-white" />
          </div>
          <p className="text-lg font-bold text-gray-900">سوق الصيدليات</p>
        </div>

        {!sent ? (
          <>
            <h1 className="text-2xl font-bold text-center mb-2">نسيت كلمة المرور؟</h1>
            <p className="text-gray-500 text-sm text-center mb-6">
              أدخل بريدك الإلكتروني وسنرسل لك رابط إعادة التعيين
            </p>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  البريد الإلكتروني
                </label>
                <input
                  {...register("email")}
                  type="email"
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 rounded-lg flex items-center justify-center gap-2 disabled:opacity-60"
              >
                {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                إرسال الرابط
              </button>
            </form>
          </>
        ) : (
          <div className="text-center">
            <CheckCircle className="h-16 w-16 text-green-500 mx-auto mb-4" />
            <h2 className="text-xl font-bold text-gray-900 mb-2">تم الإرسال!</h2>
            <p className="text-gray-600 mb-6">
              إذا كان البريد الإلكتروني مسجلاً، ستصلك رسالة تحتوي على رابط إعادة التعيين.
            </p>
          </div>
        )}

        <p className="text-center text-sm text-gray-500 mt-4">
          <Link href={`/${locale}/login`} className="text-blue-600 hover:underline">
            العودة لتسجيل الدخول
          </Link>
        </p>
      </div>
    </div>
  );
}
