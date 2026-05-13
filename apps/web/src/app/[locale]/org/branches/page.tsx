"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocale } from "next-intl";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import Shell from "@/components/layout/shell";
import { Badge } from "@/components/ui/badge";
import { branchesApi } from "@/lib/api";
import { Plus, Edit2, ChevronRight, Loader2, X, Check } from "lucide-react";

const branchSchema = z.object({
  name: z.string().min(2, "الاسم مطلوب"),
  name_ar: z.string().min(2, "الاسم العربي مطلوب"),
  address: z.string().optional(),
  phone: z.string().optional(),
  manager_name: z.string().optional(),
  storage_area_sqm: z.coerce.number().min(0).optional(),
  has_cold_storage: z.boolean().default(false),
  has_controlled_storage: z.boolean().default(false),
});

type BranchFormData = z.infer<typeof branchSchema>;

export default function BranchesPage() {
  const locale = useLocale();
  const qc = useQueryClient();
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  const { data: branches, isLoading } = useQuery({
    queryKey: ["branches"],
    queryFn: () => branchesApi.list().then((r) => r.data),
  });

  const addForm = useForm<BranchFormData>({ resolver: zodResolver(branchSchema) });
  const editForm = useForm<BranchFormData>({ resolver: zodResolver(branchSchema) });

  const createBranch = useMutation({
    mutationFn: (data: BranchFormData) => branchesApi.create(data),
    onSuccess: () => {
      toast.success("تم إنشاء الفرع");
      qc.invalidateQueries({ queryKey: ["branches"] });
      setShowAddForm(false);
      addForm.reset();
    },
    onError: () => toast.error("فشل إنشاء الفرع"),
  });

  const updateBranch = useMutation({
    mutationFn: ({ id, data }: { id: string; data: BranchFormData }) => branchesApi.update(id, data),
    onSuccess: () => {
      toast.success("تم تحديث الفرع");
      qc.invalidateQueries({ queryKey: ["branches"] });
      setEditingId(null);
    },
    onError: () => toast.error("فشل تحديث الفرع"),
  });

  const startEdit = (branch: BranchFormData & { id: string }) => {
    setEditingId(branch.id);
    editForm.reset({
      name: branch.name,
      name_ar: branch.name_ar,
      address: branch.address ?? "",
      phone: branch.phone ?? "",
      manager_name: branch.manager_name ?? "",
      storage_area_sqm: branch.storage_area_sqm,
      has_cold_storage: branch.has_cold_storage ?? false,
      has_controlled_storage: branch.has_controlled_storage ?? false,
    });
  };

  const branchList = Array.isArray(branches) ? branches : (branches?.items ?? []);

  return (
    <Shell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">الفروع</h1>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
          >
            <Plus className="h-4 w-4" />
            فرع جديد
          </button>
        </div>

        {/* Add form */}
        {showAddForm && (
          <div className="bg-white rounded-xl shadow-sm border border-blue-200 p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-gray-900">إضافة فرع جديد</h2>
              <button onClick={() => setShowAddForm(false)} className="text-gray-400 hover:text-gray-600">
                <X className="h-4 w-4" />
              </button>
            </div>
            <BranchFormFields form={addForm} />
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowAddForm(false)}
                className="px-4 py-2 border border-gray-300 text-gray-600 rounded-lg text-sm hover:bg-gray-50"
              >
                إلغاء
              </button>
              <button
                onClick={addForm.handleSubmit((d) => createBranch.mutate(d))}
                disabled={createBranch.isPending}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-60"
              >
                {createBranch.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                إنشاء الفرع
              </button>
            </div>
          </div>
        )}

        {/* Branch list */}
        {isLoading ? (
          <div className="flex items-center justify-center h-48">
            <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
          </div>
        ) : branchList.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-16 text-center">
            <p className="text-gray-500 mb-4">لا توجد فروع</p>
            <button
              onClick={() => setShowAddForm(true)}
              className="text-blue-600 hover:text-blue-700 text-sm font-medium"
            >
              إضافة فرع الآن
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {branchList.map((branch: {
              id: string;
              name: string;
              name_ar?: string;
              address?: string;
              phone?: string;
              manager_name?: string;
              storage_area_sqm?: number;
              has_cold_storage?: boolean;
              has_controlled_storage?: boolean;
              is_active: boolean;
              storage_condition_status?: string;
            }) => (
              <div key={branch.id} className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
                {editingId === branch.id ? (
                  <div className="p-6 space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="font-semibold text-gray-900">تعديل الفرع</h3>
                      <button onClick={() => setEditingId(null)} className="text-gray-400 hover:text-gray-600">
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                    <BranchFormFields form={editForm} />
                    <div className="flex gap-3 justify-end">
                      <button
                        onClick={() => setEditingId(null)}
                        className="px-4 py-2 border border-gray-300 text-gray-600 rounded-lg text-sm hover:bg-gray-50"
                      >
                        إلغاء
                      </button>
                      <button
                        onClick={editForm.handleSubmit((d) => updateBranch.mutate({ id: branch.id, data: d }))}
                        disabled={updateBranch.isPending}
                        className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-60"
                      >
                        {updateBranch.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                        حفظ
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="p-5 flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-semibold text-gray-900">{branch.name_ar ?? branch.name}</h3>
                        <Badge variant={branch.is_active ? "success" : "default"}>
                          {branch.is_active ? "نشط" : "غير نشط"}
                        </Badge>
                        {branch.storage_condition_status && (
                          <Badge variant={branch.storage_condition_status === "compliant" ? "success" : "danger"}>
                            {branch.storage_condition_status === "compliant" ? "مطابق" : "غير مطابق"}
                          </Badge>
                        )}
                      </div>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs text-gray-500">
                        {branch.address && <span>{branch.address}</span>}
                        {branch.phone && <span dir="ltr">{branch.phone}</span>}
                        {branch.manager_name && <span>المدير: {branch.manager_name}</span>}
                        {branch.storage_area_sqm && <span>مساحة التخزين: {branch.storage_area_sqm} م²</span>}
                        {branch.has_cold_storage && <span className="flex items-center gap-0.5"><Check className="h-3 w-3 text-green-500" />تخزين بارد</span>}
                        {branch.has_controlled_storage && <span className="flex items-center gap-0.5"><Check className="h-3 w-3 text-green-500" />تخزين مسيطر</span>}
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      <button
                        onClick={() => startEdit(branch as BranchFormData & { id: string })}
                        className="text-gray-400 hover:text-gray-600 p-1.5 rounded-lg hover:bg-gray-100"
                        title="تعديل"
                      >
                        <Edit2 className="h-4 w-4" />
                      </button>
                      <Link
                        href={`/${locale}/org/branches/${branch.id}`}
                        className="text-gray-400 hover:text-gray-600 p-1.5 rounded-lg hover:bg-gray-100"
                        title="التفاصيل"
                      >
                        <ChevronRight className="h-4 w-4" />
                      </Link>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </Shell>
  );
}

function BranchFormFields({ form }: { form: ReturnType<typeof useForm<BranchFormData>> }) {
  const { register, formState: { errors } } = form;
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <div>
        <label className="text-sm text-gray-600 block mb-1">اسم الفرع (عربي) *</label>
        <input {...register("name_ar")} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
        {errors.name_ar && <p className="text-red-500 text-xs mt-0.5">{errors.name_ar.message}</p>}
      </div>
      <div>
        <label className="text-sm text-gray-600 block mb-1">اسم الفرع (إنجليزي)</label>
        <input {...register("name")} dir="ltr" className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
      </div>
      <div>
        <label className="text-sm text-gray-600 block mb-1">رقم الهاتف</label>
        <input {...register("phone")} dir="ltr" className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
      </div>
      <div>
        <label className="text-sm text-gray-600 block mb-1">مدير الفرع</label>
        <input {...register("manager_name")} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
      </div>
      <div className="sm:col-span-2">
        <label className="text-sm text-gray-600 block mb-1">العنوان</label>
        <input {...register("address")} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
      </div>
      <div>
        <label className="text-sm text-gray-600 block mb-1">مساحة التخزين (م²)</label>
        <input {...register("storage_area_sqm")} type="number" min="0" dir="ltr" className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
      </div>
      <div className="flex gap-4 items-center pt-5">
        <label className="flex items-center gap-2 cursor-pointer text-sm">
          <input {...register("has_cold_storage")} type="checkbox" className="h-4 w-4 rounded" />
          تخزين بارد
        </label>
        <label className="flex items-center gap-2 cursor-pointer text-sm">
          <input {...register("has_controlled_storage")} type="checkbox" className="h-4 w-4 rounded" />
          تخزين مسيطر
        </label>
      </div>
    </div>
  );
}
