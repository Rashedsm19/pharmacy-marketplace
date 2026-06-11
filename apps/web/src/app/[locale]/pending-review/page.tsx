import { Clock, CheckCircle } from "lucide-react";
import Link from "next/link";

export default async function PendingReviewPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  return (
    <div className="min-h-screen bg-app-shell flex items-center justify-center overflow-x-hidden p-4" dir="rtl">
      <div className="w-[calc(100vw-2rem)] max-w-md min-w-0 bg-[#fffdf9]/95 rounded-3xl shadow-lift ring-1 ring-[#e2d4bf] p-10 text-center">
        <div className="flex justify-center mb-6">
          <div className="h-20 w-20 bg-[#f4eadf] rounded-full flex items-center justify-center ring-1 ring-[#e2d4bf]">
            <Clock className="h-10 w-10 text-gold-600" />
          </div>
        </div>
        <h1 className="text-2xl font-semibold text-[#1f2a24] mb-3">طلب الاعتماد قيد المراجعة</h1>
        <p className="text-[#6d746d] leading-relaxed mb-8">
          شكراً لتسجيل منشأتك في MedSave. يخضع الطلب لمراجعة بيانات الترخيص والاعتماد، وسيتم إشعارك عبر
          البريد الإلكتروني عند الموافقة خلال <strong>24–48 ساعة</strong>.
        </p>

        <div className="bg-[#f7efe3] rounded-2xl p-4 mb-6 text-right ring-1 ring-[#eadfcc]">
          <h3 className="font-semibold text-[#1f2a24] mb-2">خطوات المراجعة:</h3>
          <ul className="space-y-1 text-sm text-[#4d554e]">
            <li className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 flex-shrink-0 text-brand-600" />
              مطابقة السجل التجاري وترخيص المنشأة
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 flex-shrink-0 text-brand-600" />
              التحقق من بيانات الصيدلية والفروع
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 flex-shrink-0 text-brand-600" />
              إرسال قرار الاعتماد عبر البريد الإلكتروني
            </li>
          </ul>
        </div>

        <Link
          href={`/${locale}/login`}
          className="block w-full bg-[#1f2a24] hover:bg-brand-800 text-[#fbf7f0] font-semibold py-2.5 rounded-full transition-colors"
        >
          العودة لتسجيل الدخول
        </Link>
      </div>
    </div>
  );
}
