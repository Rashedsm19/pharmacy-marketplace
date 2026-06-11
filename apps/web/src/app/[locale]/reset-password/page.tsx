"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useLocale } from "next-intl";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { authApi } from "@/lib/api";
import { Loader2 } from "lucide-react";
import BrandLogo from "@/components/brand-logo";

const schema = z
  .object({
    new_password: z.string().min(8, "كلمة المرور يجب أن تكون 8 أحرف على الأقل"),
    confirm_password: z.string(),
  })
  .refine((d) => d.new_password === d.confirm_password, {
    message: "كلمتا المرور غير متطابقتين",
    path: ["confirm_password"],
  });

type ResetPasswordForm = z.infer<typeof schema>;

export default function ResetPasswordPage() {
  const locale = useLocale();
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordForm>({ resolver: zodResolver(schema) });

  const onSubmit = async ({ new_password }: ResetPasswordForm) => {
    try {
      await authApi.resetPassword(token, new_password);
      toast.success("تم إعادة تعيين كلمة المرور");
      router.push(`/${locale}/login`);
    } catch {
      toast.error("الرابط غير صالح أو منتهي");
    }
  };

  return (
    <div className="min-h-screen bg-app-shell flex items-center justify-center overflow-x-hidden p-4" dir="rtl">
      <div className="w-[calc(100vw-2rem)] max-w-md min-w-0 bg-[#fffdf9]/95 rounded-3xl shadow-lift ring-1 ring-[#e2d4bf] p-8">
        <div className="flex items-center justify-center gap-3 mb-8">
          <BrandLogo size="md" />
        </div>
        <h1 className="text-2xl font-semibold text-[#1f2a24] text-center mb-2">تعيين كلمة مرور جديدة</h1>
        <p className="text-[#6d746d] text-sm text-center mb-6">
          اختر كلمة مرور آمنة لحساب المنشأة.
        </p>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-[#4d554e] mb-1">
              كلمة المرور الجديدة
            </label>
            <input
              {...register("new_password")}
              type="password"
              className="w-full px-4 py-2.5 bg-[#fbf7f0]/80 border border-[#d8c8b3] rounded-full text-sm focus:outline-none focus:bg-white focus:ring-2 focus:ring-brand-500"
              dir="ltr"
            />
            {errors.new_password && (
              <p className="text-red-500 text-xs mt-1">{errors.new_password.message}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-[#4d554e] mb-1">
              تأكيد كلمة المرور
            </label>
            <input
              {...register("confirm_password")}
              type="password"
              className="w-full px-4 py-2.5 bg-[#fbf7f0]/80 border border-[#d8c8b3] rounded-full text-sm focus:outline-none focus:bg-white focus:ring-2 focus:ring-brand-500"
              dir="ltr"
            />
            {errors.confirm_password && (
              <p className="text-red-500 text-xs mt-1">{errors.confirm_password.message}</p>
            )}
          </div>
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-[#1f2a24] hover:bg-brand-800 text-[#fbf7f0] font-semibold py-2.5 rounded-full flex items-center justify-center gap-2 disabled:opacity-60"
          >
            {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
            إعادة التعيين
          </button>
        </form>
      </div>
    </div>
  );
}
