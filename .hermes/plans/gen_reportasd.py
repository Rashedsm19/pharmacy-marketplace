#!/usr/bin/env python3
# Generates /Users/rashed/phr/reportasd.pdf — read-only security & improvements report.
import re
from datetime import date

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, HRFlowable, KeepTogether,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)

pdfmetrics.registerFont(TTFont('Arabic', '/System/Library/Fonts/GeezaPro.ttc'))
pdfmetrics.registerFont(TTFont('ArabicB', '/System/Library/Fonts/GeezaPro.ttc', subfontIndex=1))

RESHAPE = re.compile(r'[\u0600-\u06FF]')
def A(t):
    if not RESHAPE.search(t):
        return t
    return get_display(arabic_reshaper.reshape(t))

NAVY = colors.HexColor('#0f2a43')
TEAL = colors.HexColor('#0e7490')
GREY = colors.HexColor('#64748b')
LIGHT = colors.HexColor('#f1f5f9')
RED = colors.HexColor('#b91c1c')
ORANGE = colors.HexColor('#c2660a')
GREEN = colors.HexColor('#15803d')

styles = {
    'h1': ParagraphStyle('h1', fontName='ArabicB', fontSize=20, textColor=NAVY, spaceAfter=6, alignment=TA_RIGHT),
    'h2': ParagraphStyle('h2', fontName='ArabicB', fontSize=14, textColor=TEAL, spaceBefore=14, spaceAfter=6, alignment=TA_RIGHT),
    'body': ParagraphStyle('body', fontName='Arabic', fontSize=11, leading=17, textColor=colors.HexColor('#1e293b'), alignment=TA_RIGHT, spaceAfter=4),
    'small': ParagraphStyle('small', fontName='Arabic', fontSize=9, leading=13, textColor=GREY, alignment=TA_RIGHT),
    'cell': ParagraphStyle('cell', fontName='Arabic', fontSize=9.5, leading=14, textColor=colors.HexColor('#1e293b'), alignment=TA_RIGHT),
    'cellb': ParagraphStyle('cellb', fontName='ArabicB', fontSize=9.5, leading=14, textColor=colors.white, alignment=TA_CENTER),
    'mono': ParagraphStyle('mono', fontName='Courier', fontSize=9, leading=13, textColor=colors.HexColor('#0f172a')),
}

def P(t, s='body'): return Paragraph(A(t), styles[s])
def M(t): return Paragraph(t, styles['mono'])

def sev(s):
    c = {'عالية': RED, 'متوسطة': ORANGE, 'منخفضة': GREEN}.get(s, GREY)
    return Paragraph(A(s), ParagraphStyle('sv', fontName='ArabicB', fontSize=9.5, textColor=c, alignment=TA_CENTER))

def table(headers, rows, widths, mono_cols=()):
    data = [[Paragraph(A(h), styles['cellb']) for h in headers]]
    for r in rows:
        data.append([c if isinstance(c, Paragraph) else Paragraph(A(str(c)), styles['mono'] if i in mono_cols else styles['cell']) for i, c in enumerate(r)])
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), TEAL),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT]),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    return t

def header_footer(canv, doc):
    canv.saveState()
    canv.setFillColor(NAVY)
    canv.rect(0, A4[1] - 12 * mm, A4[0], 12 * mm, stroke=0, fill=1)
    canv.setFont('Arabic', 9)
    canv.setFillColor(colors.white)
    canv.drawRightString(A4[0] - 15 * mm, A4[1] - 8 * mm, A('تقرير تحليل النظام — قراءة فقط'))
    canv.drawString(15 * mm, A4[1] - 8 * mm, 'Pharmacy Near-Expiry Marketplace')
    canv.setFont('Arabic', 8)
    canv.setFillColor(GREY)
    canv.drawCentredString(A4[0] / 2, 10 * mm, A(f'صفحة {doc.page}'))
    canv.restoreState()

def cover(canv, doc):
    canv.saveState()
    canv.setFillColor(NAVY)
    canv.rect(0, 0, A4[0], A4[1], stroke=0, fill=1)
    canv.setFillColor(colors.white)
    canv.setFont('ArabicB', 30)
    canv.drawCentredString(A4[0] / 2, A4[1] - 90 * mm, A('تقرير التحسينات والثغرات الأمنية'))
    canv.setFont('Arabic', 17)
    canv.drawCentredString(A4[0] / 2, A4[1] - 105 * mm, A('نظام سوق الصيدليات — قرب انتهاء الصلاحية'))
    canv.setFont('Arabic', 12)
    canv.setFillColor(colors.HexColor('#94a3b8'))
    canv.drawCentredString(A4[0] / 2, A4[1] - 130 * mm, A(f'تاريخ التقرير: {date.today().isoformat()}  —  الإصدار: commit 2ddb095'))
    canv.drawCentredString(A4[0] / 2, A4[1] - 140 * mm, A('تحليل قراءة فقط — لم يُعدّل أي ملف أو إعداد في النظام'))
    canv.setFillColor(TEAL)
    canv.rect(A4[0] / 2 - 40 * mm, A4[1] - 150 * mm, 80 * mm, 1.2, stroke=0, fill=1)
    canv.setFillColor(colors.HexColor('#94a3b8'))
    canv.setFont('Arabic', 10)
    canv.drawCentredString(A4[0] / 2, 40 * mm, A('أُعدّ آلياً بواسطة Hermes Agent — جميع النتائج مقاسة فعلياً وليست افتراضات'))
    canv.restoreState()

OUT = '/Users/rashed/phr/reportasd.pdf'
doc = BaseDocTemplate(OUT, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=20 * mm, bottomMargin=18 * mm, title='تقرير التحسينات والثغرات', author='Hermes Agent')
doc.addPageTemplates([
    PageTemplate(id='cover', frames=[Frame(0, 0, A4[0], A4[1])], onPage=cover),
    PageTemplate(id='body', frames=[Frame(doc.leftMargin, doc.bottomMargin, A4[0] - 30 * mm, A4[1] - 38 * mm)], onPage=header_footer),
])

from reportlab.platypus import NextPageTemplate, PageBreak
E = [NextPageTemplate('body'), PageBreak()]

# ── Executive summary
E.append(P('الملخص التنفيذي', 'h1'))
E.append(HRFlowable(width='100%', color=TEAL, thickness=1, spaceAfter=8))
E.append(P('أُجري فحص شامل للنظام (الواجهة، الخادم، البنية التحتية، الاختبارات) في وضع القراءة فقط. النتيجة العامة: النظام سليم وظيفياً وبناه هندسي جيد، مع 12 ملاحظة مصنفة — لا توجد ثغرات حرجة قابلة للاستغلال الفوري، وأهم الملاحظات تتعلق بإدارة الجلسات (إلغاء التوكنات) واختبار هش يفقد إشارة CI.'))
E.append(Spacer(1, 6))
E.append(table(
    ['الفحص', 'النتيجة', 'التفاصيل'],
    [
        ['lint الواجهة (ESLint)', Paragraph(A('ناجح'), ParagraphStyle('g', fontName='ArabicB', fontSize=9.5, textColor=GREEN, alignment=TA_CENTER)), 'تحذير واحد بسيط: تحميل خط مخصص في layout.tsx بدل _document'],
        ['بناء الواجهة (Next.js build)', Paragraph(A('ناجح'), ParagraphStyle('g', fontName='ArabicB', fontSize=9.5, textColor=GREEN, alignment=TA_CENTER)), 'جميع المسارات تُبنى بنجاح'],
        ['اختبارات الخادم (pytest)', Paragraph(A('157 / 158'), ParagraphStyle('o', fontName='ArabicB', fontSize=9.5, textColor=ORANGE, alignment=TA_CENTER)), 'اختبار واحد هش (شرح لاحقاً) — لا عيب منتج'],
        ['حالة المستودع (git)', Paragraph(A('نظيف'), ParagraphStyle('g', fontName='ArabicB', fontSize=9.5, textColor=GREEN, alignment=TA_CENTER)), 'فرع main محدث، لا ملفات معدلة'],
    ],
    [45 * mm, 25 * mm, None], mono_cols=(),
))
E.append(Spacer(1, 8))
E.append(table(
    ['الخطورة', 'العدد'],
    [[sev('عالية'), '0'], [sev('متوسطة'), '3'], [sev('منخفضة'), '9']],
    [60 * mm, 30 * mm],
))

# ── Strengths
E.append(P('نقاط القوة المُتحقق منها (بإحداثيات الكود)', 'h1'))
E.append(HRFlowable(width='100%', color=TEAL, thickness=1, spaceAfter=8))
E.append(table(
    ['المجال', 'التفاصيل', 'الموقع'],
    [
        ['تشفير كلمات المرور', 'Argon2 بإعدادات قوية (hash_len=32)', 'apps/api/auth/password.py'],
        ['رموز الدخول', 'JWT مع حقل jti فريد + فصل صلاحية access/refresh', 'apps/api/auth/jwt.py:58'],
        ['حجب المعلّقين', 'منع تجديد التوكن للمنشآت الموقوفة (سد نافذة 7 أيام)', 'apps/api/services/auth_service.py'],
        ['استعادة المرور', 'رسالة موحدة تمنع كشف البريدات + توكن reset مشفر با哈expiry', 'apps/api/services/auth_service.py:234'],
        ['حد محاولات الدخول', 'Throttle لكل مسار مع Retry-After بالعربية + nginx limit_req', 'apps/api/middleware/throttle.py'],
        ['ملفات الرفع', 'قائمة امتدادات مسموحة + فحص بايتات zip + حد حجم', 'services/integrations/storage_service.py:156'],
        ['سجل التدقيق', 'Audit logging موزع على الإداري والدعم والقوائم', 'apps/api/services/audit_service.py'],
        ['انتحال الهوية', 'سبب إلزامي + جلسات مراجعة + منع إنشاء API keys + منع استهداف مدير', 'routers/support/impersonation.py'],
        ['سلسلة التبريد', 'سجل حرارة إلزامي قبل الصرف (مُختبر)', 'tests/test_cold_chain.py'],
        ['بذور آمنة', 'رفض كلمات مرور افتراضية في الإنتاج + SEED_ON_STARTUP=false', 'seeds/seed.py:68, render.yaml'],
    ],
    [32 * mm, None, 52 * mm],
))

# ── Findings
E.append(P('الثغرات والمشاكل — مصنفة بالخطورة', 'h1'))
E.append(HRFlowable(width='100%', color=TEAL, thickness=1, spaceAfter=8))

E.append(P('متوسطة الخطورة', 'h2'))
E.append(table(
    ['#', 'المشكلة', 'الوصف والتوصية', 'الموقع'],
    [
        [sev('متوسطة'), 'إلغاء الدخول بلا حماية خادمية (Logout)', 'الخروج مجرد رمي التوكن في العميل؛ توكن مسروق يبقى صالحاً حتى انتهائه. حقل jti موجود لكن دون قائمة إبطال. التوصية: denylist للـ jti (Redis أو جدول DB)', 'routers/auth.py:43'],
        [sev('متوسطة'), 'لا تدوير لرموز التجديد (Refresh Rotation)', 'نفس refresh token قابل لإعادة الاستخدام حتى 7 أيام — سرقته تعني جلسة دائمة. التوصية: تدوير مع كل استخدام + كشف إعادة الاستخدام', 'services/auth_service.py:190'],
        [sev('متوسطة'), 'اختبار هش يفقد إشارة CI', 'test_the_dashboard_summarises_every_customer يفترض أن منشأة لها مخزون داخل أول 50 صفاً مرتبة بالأحدث؛ ~65 منشأة أنشأتها اختبارات أخرى تدفعها خارج الصفحة. ينجح وحده ويفشل مع الجلسة الكاملة. التوصية: البحث عبر كل الصفحات أو ترتيب ثابت', 'tests/test_support_actions.py:291'],
    ],
    [18 * mm, 32 * mm, None, 34 * mm],
))

E.append(P('منخفضة الخطورة', 'h2'))
E.append(table(
    ['#', 'المشكلة', 'الوصف والتوصية', 'الموقع'],
    [
        [sev('منخفضة'), 'قيم افتراضية غير آمنة للمفاتيح', 'SECRET_KEY وJWT_SECRET_KEY لها قيم fallback؛ يفضل فشل الإقلاع في الإنتاج إذا لم تُضبط', 'config.py:26,52'],
        [sev('منخفضة'), 'لا ترويسات أمان من الخادم نفسه', 'X-Frame-Options وغيرها في nginx فقط؛ لا HSTS ولا CSP في أي مكان', 'infra/docker/nginx.conf:59'],
        [sev('منخفضة'), 'Throttle داخل العملية الواحدة', 'الحد لكل instance — يتضاعف فعلياً مع تعدد العمال. يكفي حالياً؛ يلزم Redis عند التوسع', 'middleware/throttle.py'],
        [sev('منخفضة'), 'رابط قاعدة بيانات الاختبار مثبّت', 'يفترض postgres:postgres محلياً — يفشل على أجهزة أخرى (أعيد إنتاجه: 158 خطأ). التوصية: السماح بتجاوز DATABASE_URL', 'tests/conftest.py:23'],
        [sev('منخفضة'), 'جدول listing_views بلا مسار كتابة', 'مذكور في نموذج البيانات لكن لا يوجد router يسجّل المشاهدات — ميزة عدّ المشاهدات معطلة', 'نموذج البيانات'],
        [sev('منخفضة'), 'بقايا اختبارات في قاعدة البيانات المحلية', '67 منشأة معظمها نواتج اختبارات (Sahha Pharmacies {hash}) دون استراتيجية تنظيف بين الجلسات', 'قاعدة pharmacy_test المحلية'],
        [sev('منخفضة'), 'تحذير lint بسيط', 'خط مخصص يحمّل في layout بدل _document — يحمّل لكل صفحة عملياً، لكنه نمط غير موصى به', 'src/app/[locale]/layout.tsx:35'],
        [sev('منخفضة'), 'ملاحظة: .env.render', 'موجود في جذر المشروع لكنه مستثنى من git بشكل صحيح وصلاحياته 600 — لا إجراء مطلوب', 'مؤكد بـ git check-ignore'],
        [sev('منخفضة'), 'نطاق غير مفحوص عميقاً', 'لم يُفحص هذا الجلسة بعمق: واجهة العروض/الحجوزات، جرس الإشعارات، RTL — يوصى بجولة QA مستقبلية', '—'],
    ],
    [18 * mm, 32 * mm, None, 34 * mm],
))

# ── Roadmap
E.append(P('خارطة التحسين بالأولوية', 'h1'))
E.append(HRFlowable(width='100%', color=TEAL, thickness=1, spaceAfter=8))
E.append(table(
    ['الأولوية', 'الإجراء', 'الجهد التقديري'],
    [
        [Paragraph(A('P1 — فوري'), ParagraphStyle('p1', fontName='ArabicB', fontSize=9.5, textColor=RED, alignment=TA_CENTER)),
         'إصلاح الاختبار الهش + السماح بتجاوز رابط قاعدة الاختبار', 'ساعة واحدة'],
        [Paragraph(A('P1 — فوري'), ParagraphStyle('p1', fontName='ArabicB', fontSize=9.5, textColor=RED, alignment=TA_CENTER)),
         'قائمة إبطال التوكنات (jti) + تدوير refresh tokens', '2–3 أيام'],
        [Paragraph(A('P2 — قريب'), ParagraphStyle('p2', fontName='ArabicB', fontSize=9.5, textColor=ORANGE, alignment=TA_CENTER)),
         'فحص إلزامي للمفاتيح عند الإقلاع + HSTS/CSP في nginx + ترويسات أمان', 'يوم واحد'],
        [Paragraph(A('P2 — قريب'), ParagraphStyle('p2', fontName='ArabicB', fontSize=9.5, textColor=ORANGE, alignment=TA_CENTER)),
         'نقل Throttle إلى مخزن مركزي عند التوسع لأكثر من instance', '1–2 يوم'],
        [Paragraph(A('P3 — لاحق'), ParagraphStyle('p3', fontName='ArabicB', fontSize=9.5, textColor=GREEN, alignment=TA_CENTER)),
         'تفعيل أو حذف listing_views + تنظيف بقايا الاختبارات + إصلاح تحذير الخط + جولة QA للواجهة', 'حسب الأولوية'],
    ],
    [22 * mm, None, 28 * mm],
))

E.append(Spacer(1, 10))
E.append(P('المنهجية والحدود: جميع النتائج أعلاه مقاسة فعلياً في جلسة التحليل (تشغيل lint وbuild وpytest، وقراءة الكود بإحداثياته، وفحص قاعدة البيانات). لم يُعدّل أو يُحذف أي ملف أو إعداد في النظام — هذا التقرير قراءة فقط. ملاحظة أمنية على التقرير نفسه: يُنصح بعدم مشاركته علناً لأنه يوثق نقاط الضعف بمواقعها.', 'small'))

doc.build(E)
print('PDF generated:', OUT)
