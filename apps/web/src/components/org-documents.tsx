"use client";

import { useRef, useState } from "react";
import { FileText, Upload, Download, Trash2, CheckCircle2, AlertCircle } from "lucide-react";
import { toast } from "sonner";

import { organizationsApi } from "@/lib/api";

type DocType = "cr" | "license";

const LABELS: Record<DocType, string> = {
  cr: "السجل التجاري",
  license: "رخصة المنشأة الصيدلانية",
};

/** Opens the authenticated download in a new tab without leaking the token. */
async function openDocument(orgId: string, docType: DocType) {
  try {
    const { data } = await organizationsApi.downloadDocument(orgId, docType);
    const url = URL.createObjectURL(data as Blob);
    window.open(url, "_blank", "noopener");
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch {
    toast.error("تعذر فتح المستند");
  }
}

/** Read-only view used by the admin reviewer. */
export function OrgDocumentsView({
  orgId,
  crDoc,
  licenseDoc,
}: {
  orgId: string;
  crDoc?: string | null;
  licenseDoc?: string | null;
}) {
  const rows: { type: DocType; stored?: string | null }[] = [
    { type: "cr", stored: crDoc },
    { type: "license", stored: licenseDoc },
  ];

  return (
    <div className="flex flex-col gap-2">
      {rows.map(({ type, stored }) => (
        <div
          key={type}
          className="flex items-center justify-between gap-3 rounded-lg border border-[#e8dfcf] bg-white px-3 py-2"
        >
          <span className="flex items-center gap-2 text-sm text-[#1f2823]">
            <FileText className="h-4 w-4 text-[#8a938e]" />
            {LABELS[type]}
          </span>
          {stored ? (
            <button
              type="button"
              onClick={() => openDocument(orgId, type)}
              className="flex items-center gap-1.5 rounded-md bg-[#e4f7f5] px-2.5 py-1 text-xs font-bold text-[#066a65] hover:bg-[#d3f1ee]"
            >
              <Download className="h-3.5 w-3.5" />
              عرض
            </button>
          ) : (
            <span className="flex items-center gap-1.5 text-xs font-bold text-[#b45309]">
              <AlertCircle className="h-3.5 w-3.5" />
              لم يرفع
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

/** Upload/replace view used by the organization itself. */
export function OrgDocumentsUpload({
  orgId,
  crDoc,
  licenseDoc,
  onChanged,
}: {
  orgId: string;
  crDoc?: string | null;
  licenseDoc?: string | null;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState<DocType | null>(null);
  const inputs = {
    cr: useRef<HTMLInputElement>(null),
    license: useRef<HTMLInputElement>(null),
  };

  const upload = async (docType: DocType, file: File | undefined) => {
    if (!file) return;
    setBusy(docType);
    try {
      await organizationsApi.uploadDocument(docType, file);
      toast.success(`تم رفع ${LABELS[docType]}`);
      onChanged();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(typeof msg === "string" ? msg : "تعذر رفع المستند");
    } finally {
      setBusy(null);
      if (inputs[docType].current) inputs[docType].current.value = "";
    }
  };

  const remove = async (docType: DocType) => {
    setBusy(docType);
    try {
      await organizationsApi.deleteDocument(docType);
      toast.success("تم حذف المستند");
      onChanged();
    } catch {
      toast.error("تعذر حذف المستند");
    } finally {
      setBusy(null);
    }
  };

  const rows: { type: DocType; stored?: string | null }[] = [
    { type: "cr", stored: crDoc },
    { type: "license", stored: licenseDoc },
  ];

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-[#55605b]">
        يراجع فريق المنصة هذه المستندات قبل اعتماد المنشأة. الصيغ المقبولة PDF أو JPG أو PNG،
        بحد أقصى 10 ميجابايت للملف.
      </p>

      {rows.map(({ type, stored }) => (
        <div
          key={type}
          className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#e8dfcf] bg-white px-4 py-3"
        >
          <div className="flex items-center gap-2.5">
            {stored ? (
              <CheckCircle2 className="h-5 w-5 flex-none text-[#15803d]" />
            ) : (
              <AlertCircle className="h-5 w-5 flex-none text-[#b45309]" />
            )}
            <div>
              <p className="text-sm font-bold text-[#1f2823]">{LABELS[type]}</p>
              <p className="text-xs text-[#8a938e]">{stored ? "مرفوع" : "مطلوب للاعتماد"}</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {stored && (
              <>
                <button
                  type="button"
                  onClick={() => openDocument(orgId, type)}
                  className="flex items-center gap-1.5 rounded-lg border border-[#cdbda8] px-3 py-1.5 text-xs font-bold text-[#4d554e] hover:bg-[#f4eadf]"
                >
                  <Download className="h-3.5 w-3.5" />
                  عرض
                </button>
                <button
                  type="button"
                  onClick={() => remove(type)}
                  disabled={busy === type}
                  className="flex items-center gap-1.5 rounded-lg border border-[#f0c9c7] px-3 py-1.5 text-xs font-bold text-[#b4231f] hover:bg-[#fbe7e5] disabled:opacity-50"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  حذف
                </button>
              </>
            )}
            <input
              ref={inputs[type]}
              type="file"
              accept="application/pdf,image/jpeg,image/png"
              className="hidden"
              onChange={(e) => upload(type, e.target.files?.[0])}
            />
            <button
              type="button"
              onClick={() => inputs[type].current?.click()}
              disabled={busy === type}
              className="flex items-center gap-1.5 rounded-lg bg-[#0aa39b] px-3 py-1.5 text-xs font-bold text-white hover:bg-[#07877f] disabled:opacity-50"
            >
              <Upload className="h-3.5 w-3.5" />
              {busy === type ? "جار الرفع…" : stored ? "استبدال" : "رفع"}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
