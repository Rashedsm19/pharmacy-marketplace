"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import Shell from "@/components/layout/shell";
import { Badge } from "@/components/ui/badge";
import { productsApi } from "@/lib/api";
import { Loader2, Tag, Edit2, Check, X } from "lucide-react";

type CategoryEditState = {
  is_exchange_allowed_default: boolean;
  is_restricted: boolean;
  requires_cold_storage: boolean;
};

export default function AdminCategoriesPage() {
  const qc = useQueryClient();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editState, setEditState] = useState<CategoryEditState | null>(null);

  const { data: categories, isLoading } = useQuery({
    queryKey: ["categories-admin"],
    queryFn: () => productsApi.listCategories().then((r) => r.data),
  });

  const updateCategory = useMutation({
    mutationFn: ({ id, data }: { id: string; data: CategoryEditState }) =>
      productsApi.updateCategory(id, data),
    onSuccess: () => {
      toast.success("تم تحديث الفئة");
      qc.invalidateQueries({ queryKey: ["categories-admin"] });
      setEditingId(null);
    },
    onError: () => toast.error("فشل تحديث الفئة"),
  });

  const cats = Array.isArray(categories) ? categories : (categories?.items ?? []);

  return (
    <Shell>
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Tag className="h-6 w-6 text-purple-600" />
          <h1 className="text-2xl font-bold text-gray-900">قواعد الفئات المحظورة</h1>
        </div>

        <p className="text-sm text-gray-500">
          تحكم في الفئات المسموح بها في السوق. يمكن تعطيل التبادل لفئة معينة أو تحديدها كفئة مقيدة.
        </p>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
            </div>
          ) : cats.length === 0 ? (
            <div className="text-center py-16 text-gray-500">لا توجد فئات</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الفئة</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">التبادل مسموح</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">مقيدة</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">تخزين بارد</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">عدد المنتجات</th>
                  <th className="text-right px-4 py-3 text-xs text-gray-500 font-medium">الإجراءات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {cats.map((cat: {
                  id: string;
                  name_ar?: string;
                  name: string;
                  is_exchange_allowed_default: boolean;
                  is_restricted: boolean;
                  requires_cold_storage: boolean;
                  product_count?: number;
                }) => (
                  <tr key={cat.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">{cat.name_ar ?? cat.name}</td>
                    {editingId === cat.id && editState ? (
                      <>
                        <td className="px-4 py-3">
                          <input
                            type="checkbox"
                            checked={editState.is_exchange_allowed_default}
                            onChange={(e) => setEditState({ ...editState, is_exchange_allowed_default: e.target.checked })}
                            className="h-4 w-4 rounded"
                          />
                        </td>
                        <td className="px-4 py-3">
                          <input
                            type="checkbox"
                            checked={editState.is_restricted}
                            onChange={(e) => setEditState({ ...editState, is_restricted: e.target.checked })}
                            className="h-4 w-4 rounded"
                          />
                        </td>
                        <td className="px-4 py-3">
                          <input
                            type="checkbox"
                            checked={editState.requires_cold_storage}
                            onChange={(e) => setEditState({ ...editState, requires_cold_storage: e.target.checked })}
                            className="h-4 w-4 rounded"
                          />
                        </td>
                        <td className="px-4 py-3 text-gray-400">{cat.product_count ?? 0}</td>
                        <td className="px-4 py-3">
                          <div className="flex gap-1.5">
                            <button
                              onClick={() => updateCategory.mutate({ id: cat.id, data: editState })}
                              disabled={updateCategory.isPending}
                              className="flex items-center gap-1 px-2 py-1 bg-green-600 hover:bg-green-700 text-white rounded text-xs"
                            >
                              <Check className="h-3 w-3" />
                              حفظ
                            </button>
                            <button
                              onClick={() => setEditingId(null)}
                              className="flex items-center gap-1 px-2 py-1 border border-gray-300 text-gray-600 rounded text-xs hover:bg-gray-50"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </div>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="px-4 py-3">
                          <Badge variant={cat.is_exchange_allowed_default ? "success" : "danger"}>
                            {cat.is_exchange_allowed_default ? "مسموح" : "ممنوع"}
                          </Badge>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={cat.is_restricted ? "warning" : "default"}>
                            {cat.is_restricted ? "مقيدة" : "عادية"}
                          </Badge>
                        </td>
                        <td className="px-4 py-3">
                          {cat.requires_cold_storage ? (
                            <Badge variant="info">مطلوب</Badge>
                          ) : (
                            <span className="text-gray-400 text-xs">لا</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-gray-500">{cat.product_count ?? 0}</td>
                        <td className="px-4 py-3">
                          <button
                            onClick={() => {
                              setEditingId(cat.id);
                              setEditState({
                                is_exchange_allowed_default: cat.is_exchange_allowed_default,
                                is_restricted: cat.is_restricted,
                                requires_cold_storage: cat.requires_cold_storage,
                              });
                            }}
                            className="text-blue-600 hover:text-blue-700 p-1 rounded"
                          >
                            <Edit2 className="h-4 w-4" />
                          </button>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </Shell>
  );
}
