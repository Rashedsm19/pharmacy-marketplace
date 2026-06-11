"use client";

import { useState } from "react";
import { Search, ChevronRight, ChevronLeft } from "lucide-react";
import { cn } from "@/lib/utils";

export interface Column<T> {
  key: string;
  header: string;
  render?: (row: T) => React.ReactNode;
  sortable?: boolean;
  hiddenOnMobile?: boolean;
  align?: "right" | "left" | "center";
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  total?: number;
  page?: number;
  pageSize?: number;
  onPageChange?: (page: number) => void;
  searchPlaceholder?: string;
  onSearch?: (q: string) => void;
  isLoading?: boolean;
  emptyMessage?: string;
  rowKey: (row: T) => string;
  actions?: (row: T) => React.ReactNode;
  minWidthClass?: string;
}

export function DataTable<T>({
  columns,
  data,
  total = 0,
  page = 1,
  pageSize = 20,
  onPageChange,
  searchPlaceholder = "بحث...",
  onSearch,
  isLoading,
  emptyMessage = "لا توجد بيانات",
  rowKey,
  actions,
  minWidthClass = "min-w-[640px]",
}: DataTableProps<T>) {
  const [searchVal, setSearchVal] = useState("");
  const totalPages = Math.ceil(total / pageSize);

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchVal(e.target.value);
    onSearch?.(e.target.value);
  };

  const alignClass = (a?: Column<T>["align"]) =>
    a === "left" ? "text-left" : a === "center" ? "text-center" : "text-right";

  return (
    <div className="bg-white/90 ring-1 ring-[#e1d3c0] shadow-soft rounded-2xl overflow-hidden">
      {/* Search bar */}
      {onSearch && (
        <div className="p-4 border-b border-[#eadfcc]">
          <div className="relative">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#a88d60]" />
            <input
              value={searchVal}
              onChange={handleSearch}
              placeholder={searchPlaceholder}
              className="w-full pr-10 pl-4 h-10 bg-[#fbf7f0]/80 ring-1 ring-inset ring-[#d8c8b3] rounded-full text-sm placeholder:text-[#9a8b77] focus:outline-none focus:bg-white focus:ring-2 focus:ring-brand-500"
            />
          </div>
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto">
        <table className={cn("w-full text-sm tabular-nums", minWidthClass)}>
          <thead className="bg-[#f7efe3] border-b border-[#eadfcc]">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={cn(
                    "px-4 py-3 text-[11px] uppercase tracking-normal font-semibold text-[#7d6d58] whitespace-nowrap",
                    alignClass(col.align),
                    col.hiddenOnMobile && "hidden md:table-cell"
                  )}
                >
                  {col.header}
                </th>
              ))}
              {actions && (
                <th className="px-4 py-3 text-[11px] uppercase tracking-normal font-semibold text-[#7d6d58] text-right">
                  الإجراءات
                </th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#eadfcc]/80">
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="animate-pulse">
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={cn(
                        "px-4 py-3",
                        col.hiddenOnMobile && "hidden md:table-cell"
                      )}
                    >
                      <div className="h-4 bg-[#f0e4d4] rounded w-3/4" />
                    </td>
                  ))}
                  {actions && (
                    <td className="px-4 py-3">
                      <div className="h-4 bg-[#f0e4d4] rounded w-1/2" />
                    </td>
                  )}
                </tr>
              ))
            ) : data.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length + (actions ? 1 : 0)}
                  className="px-4 py-12 text-center text-[#9a8b77]"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              data.map((row) => (
                <tr
                  key={rowKey(row)}
                  className="hover:bg-[#fbf7f0]/70 transition-colors"
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={cn(
                        "px-4 py-3 text-[#4d554e]",
                        alignClass(col.align),
                        col.hiddenOnMobile && "hidden md:table-cell"
                      )}
                    >
                      {col.render
                        ? col.render(row)
                        : String((row as Record<string, unknown>)[col.key] ?? "—")}
                    </td>
                  ))}
                  {actions && (
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5 justify-end">
                        {actions(row)}
                      </div>
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && onPageChange && (
        <div className="p-4 border-t border-[#eadfcc] flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <p className="text-xs sm:text-sm text-[#6d746d] tabular-nums">
            {total.toLocaleString("ar-SA")} نتيجة — صفحة {page} من {totalPages}
          </p>
          <div className="flex items-center gap-1 self-end sm:self-auto">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              aria-label="الصفحة السابقة"
              className="h-8 w-8 inline-flex items-center justify-center rounded-full ring-1 ring-[#d8c8b3] text-[#6d746d] hover:bg-[#f7efe3] disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              const p = Math.max(1, Math.min(page - 2, totalPages - 4)) + i;
              return (
                <button
                  key={p}
                  onClick={() => onPageChange(p)}
                  className={cn(
                    "h-8 w-8 rounded-lg text-xs font-semibold tabular-nums transition-colors",
                    p === page
                      ? "bg-[#1f2a24] text-[#fbf7f0] shadow-sm"
                      : "text-[#6d746d] hover:bg-[#f7efe3]"
                  )}
                >
                  {p}
                </button>
              );
            })}
            <button
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
              aria-label="الصفحة التالية"
              className="h-8 w-8 inline-flex items-center justify-center rounded-full ring-1 ring-[#d8c8b3] text-[#6d746d] hover:bg-[#f7efe3] disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
