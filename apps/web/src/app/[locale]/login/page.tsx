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
import { ShieldCheck, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import BrandLogo from "@/components/brand-logo";

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
      className="min-h-screen flex items-center justify-center overflow-x-hidden p-4 sm:p-6 bg-app-shell"
      style={{
        background:
          "radial-gradient(60% 48% at 80% 0%, rgba(217,155,22,0.13) 0%, rgba(217,155,22,0) 52%), radial-gradient(48% 38% at 0% 100%, rgba(10,163,155,0.09) 0%, rgba(10,163,155,0) 54%), linear-gradient(180deg, #FBF7F0 0%, #FFFDF9 100%)",
      }}
      dir="rtl"
    >
      <div className="w-[calc(100vw-2rem)] max-w-md min-w-0">
        {/* Brand lockup */}
        <div className="flex items-center justify-center gap-3 mb-7">
          <BrandLogo size="lg" />
        </div>

        {/* Card */}
        <div className="bg-[#fffdf9]/95 rounded-3xl shadow-lift ring-1 ring-[#e2d4bf] p-7 sm:p-8">
          <div className="mb-6">
            <h1 className="text-xl font-semibold text-[#1f2a24]">
              دخول المنشآت المعتمدة
            </h1>
            <p className="text-sm text-[#6d746d] mt-1 leading-relaxed">
              أدِر المخزون القابل للتداول والعروض والتقارير التشغيلية من لوحة موحدة.
            </p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-[#4d554e] mb-1.5">
                {t("email")}
              </label>
              <input
                type="email"
                {...register("email")}
                className="w-full h-11 px-4 bg-[#fbf7f0]/80 ring-1 ring-inset ring-[#d8c8b3] rounded-full text-sm placeholder:text-[#9a8b77] focus:outline-none focus:bg-white focus:ring-2 focus:ring-brand-500 transition-colors"
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
                <label className="block text-xs font-medium text-[#4d554e]">
                  {t("password")}
                </label>
                <Link
                  href={`/${locale}/forgot-password`}
                  className="text-xs text-brand-700 hover:text-brand-800 hover:underline"
                >
                  {t("forgotPassword")}
                </Link>
              </div>
              <input
                type="password"
                {...register("password")}
                className="w-full h-11 px-4 bg-[#fbf7f0]/80 ring-1 ring-inset ring-[#d8c8b3] rounded-full text-sm placeholder:text-[#9a8b77] focus:outline-none focus:bg-white focus:ring-2 focus:ring-brand-500 transition-colors"
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

          <p className="text-center text-sm text-[#6d746d] mt-6">
            {t("noAccount")}{" "}
            <Link
              href={`/${locale}/register`}
              className="text-brand-700 font-medium hover:text-brand-800 hover:underline"
            >
              {t("register")}
            </Link>
          </p>
        </div>

        {/* Trust hint */}
        <div className="mt-5 flex items-center justify-center gap-2 text-[11px] text-[#6d746d]">
          <ShieldCheck className="h-3.5 w-3.5 text-brand-600" />
          <span>منصة سعودية مخصصة للصيدليات والمنشآت الصحية المرخصة</span>
        </div>
      </div>
    </div>
  );
}
