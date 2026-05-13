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
import { Pill, ShieldCheck, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

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
      const { access_token, refresh_token, org_id } = res.data;
      setTokens(access_token, refresh_token);
      const meRes = await authApi.me();
      setUser({ ...meRes.data, org_id });
      router.push(`/${locale}/dashboard`);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg ?? "فشل تسجيل الدخول");
    }
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4 sm:p-6"
      style={{
        background:
          "radial-gradient(60% 50% at 80% 0%, rgba(99,102,241,0.10) 0%, rgba(99,102,241,0) 50%), radial-gradient(50% 40% at 0% 100%, rgba(245,158,11,0.08) 0%, rgba(245,158,11,0) 50%), linear-gradient(180deg, #FAFBFC 0%, #FFFFFF 100%)",
      }}
      dir="rtl"
    >
      <div className="w-full max-w-md">
        {/* Brand lockup */}
        <div className="flex items-center justify-center gap-3 mb-7">
          <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center shadow-lift">
            <Pill className="h-6 w-6 text-white" />
          </div>
          <div className="text-right">
            <p className="text-lg font-bold text-slate-900 leading-tight">
              سوق الصيدليات
            </p>
            <p className="text-[11px] text-slate-500 leading-tight">
              Near-Expiry B2B Marketplace
            </p>
          </div>
        </div>

        {/* Card */}
        <div className="bg-white rounded-3xl shadow-lift ring-1 ring-slate-200/70 p-7 sm:p-8">
          <div className="mb-6">
            <h1 className="text-xl font-bold text-slate-900">
              {t("login")}
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              سجّل الدخول للوصول إلى لوحة التحكم
            </p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1.5">
                {t("email")}
              </label>
              <input
                type="email"
                {...register("email")}
                className="w-full h-11 px-4 bg-slate-50/60 ring-1 ring-inset ring-slate-200 rounded-lg text-sm placeholder:text-slate-400 focus:outline-none focus:bg-white focus:ring-2 focus:ring-brand-500 transition-colors"
                placeholder="example@pharmacy.sa"
                dir="ltr"
                autoComplete="email"
              />
              {errors.email && (
                <p className="text-rose-600 text-xs mt-1">{errors.email.message}</p>
              )}
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-medium text-slate-700">
                  {t("password")}
                </label>
                <Link
                  href={`/${locale}/forgot-password`}
                  className="text-xs text-brand-600 hover:text-brand-700 hover:underline"
                >
                  {t("forgotPassword")}
                </Link>
              </div>
              <input
                type="password"
                {...register("password")}
                className="w-full h-11 px-4 bg-slate-50/60 ring-1 ring-inset ring-slate-200 rounded-lg text-sm placeholder:text-slate-400 focus:outline-none focus:bg-white focus:ring-2 focus:ring-brand-500 transition-colors"
                placeholder="••••••••"
                dir="ltr"
                autoComplete="current-password"
              />
              {errors.password && (
                <p className="text-rose-600 text-xs mt-1">{errors.password.message}</p>
              )}
            </div>

            <Button
              type="submit"
              variant="primary"
              size="lg"
              fullWidth
              loading={isSubmitting}
            >
              {t("loginButton")}
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </form>

          <p className="text-center text-sm text-slate-600 mt-6">
            {t("noAccount")}{" "}
            <Link
              href={`/${locale}/register`}
              className="text-brand-600 font-medium hover:text-brand-700 hover:underline"
            >
              {t("register")}
            </Link>
          </p>
        </div>

        {/* Trust hint */}
        <div className="mt-5 flex items-center justify-center gap-2 text-[11px] text-slate-500">
          <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
          <span>منصة B2B خاصة بالصيدليات المرخصة في المملكة</span>
        </div>
      </div>
    </div>
  );
}
