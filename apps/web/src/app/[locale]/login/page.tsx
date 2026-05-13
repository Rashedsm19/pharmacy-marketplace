"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslations, useLocale } from "next-intl";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/lib/auth";
import { Pill, Loader2 } from "lucide-react";

const loginSchema = z.object({
  email: z.string().email("البريد الإلكتروني غير صحيح"),
  password: z.string().min(8, "كلمة المرور يجب أن تكون 8 أحرف على الأقل"),
});

type LoginForm = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const t = useTranslations("auth");
  const locale = useLocale();
  const router = useRouter();
  const { setUser, setTokens } = useAuthStore();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({ resolver: zodResolver(loginSchema) });

  const onSubmit = async (data: LoginForm) => {
    try {
      const res = await authApi.login(data.email, data.password);
      const { access_token, refresh_token, user_id, role, org_id } = res.data;
      setTokens(access_token, refresh_token);

      // Fetch user profile
      const meRes = await authApi.me();
      setUser({ ...meRes.data, org_id });
      router.push(`/${locale}/dashboard`);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg ?? "فشل تسجيل الدخول");
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4" dir="rtl">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-6 sm:p-8">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="h-12 w-12 bg-blue-600 rounded-xl flex items-center justify-center">
            <Pill className="h-6 w-6 text-white" />
          </div>
          <div className="text-right">
            <p className="text-xl font-bold text-gray-900">سوق الصيدليات</p>
            <p className="text-xs text-gray-500">Pharmacy Near-Expiry Marketplace</p>
          </div>
        </div>

        <h1 className="text-2xl font-bold text-gray-900 mb-6 text-center">
          {t("login")}
        </h1>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t("email")}
            </label>
            <input
              type="email"
              {...register("email")}
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="example@pharmacy.sa"
              dir="ltr"
            />
            {errors.email && (
              <p className="text-red-500 text-xs mt-1">{errors.email.message}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t("password")}
            </label>
            <input
              type="password"
              {...register("password")}
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="••••••••"
              dir="ltr"
            />
            {errors.password && (
              <p className="text-red-500 text-xs mt-1">{errors.password.message}</p>
            )}
          </div>

          <div className="flex justify-end">
            <Link
              href={`/${locale}/forgot-password`}
              className="text-sm text-blue-600 hover:underline"
            >
              {t("forgotPassword")}
            </Link>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 px-4 rounded-lg flex items-center justify-center gap-2 transition-colors disabled:opacity-60"
          >
            {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
            {t("loginButton")}
          </button>
        </form>

        <p className="text-center text-sm text-gray-600 mt-6">
          {t("noAccount")}{" "}
          <Link href={`/${locale}/register`} className="text-blue-600 font-medium hover:underline">
            {t("register")}
          </Link>
        </p>
      </div>
    </div>
  );
}
