import { Clock, CheckCircle } from "lucide-react";
import Link from "next/link";

export default function PendingReviewPage({
  params,
}: {
  params: { locale: string };
}) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4" dir="rtl">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-10 text-center">
        <div className="flex justify-center mb-6">
          <div className="h-20 w-20 bg-amber-100 rounded-full flex items-center justify-center">
            <Clock className="h-10 w-10 text-amber-600" />
          </div>
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-3">طلبك قيد المراجعة</h1>
        <p className="text-gray-600 leading-relaxed mb-8">
          شكراً لتسجيلك في سوق الصيدليات. يخضع طلبك حالياً للمراجعة من قبل فريقنا وسيتم إعلامك عبر
          البريد الإلكتروني عند الموافقة خلال <strong>24–48 ساعة</strong>.
        </p>

        <div className="bg-blue-50 rounded-xl p-4 mb-6 text-right">
          <h3 className="font-semibold text-blue-900 mb-2">ما يمكنك توقعه:</h3>
          <ul className="space-y-1 text-sm text-blue-700">
            <li className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 flex-shrink-0" />
              مراجعة وثائق التسجيل التجاري والترخيص
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 flex-shrink-0" />
              التحقق من معلومات الصيدلية
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 flex-shrink-0" />
              إرسال تأكيد الموافقة عبر البريد الإلكتروني
            </li>
          </ul>
        </div>

        <Link
          href={`/${params.locale}/login`}
          className="block w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 rounded-lg transition-colors"
        >
          العودة لتسجيل الدخول
        </Link>
      </div>
    </div>
  );
}
