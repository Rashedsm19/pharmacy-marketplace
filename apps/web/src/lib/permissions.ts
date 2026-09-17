/**
 * Who may do what, on the client.
 *
 * The server is the authority — every guarded endpoint checks again — so this
 * exists only to hide links and buttons that would answer 403. A platform
 * administrator passes everything. A session stored before permissions were
 * sent (no `permissions` field at all) is treated as unrestricted, so nobody
 * loses their sidebar on the deploy that introduced roles.
 */
import { useAuthStore, type AuthUser } from "@/lib/auth";

export function hasPermission(user: AuthUser | null | undefined, ...keys: string[]): boolean {
  if (!user) return false;
  if (user.role === "super_admin") return true;
  if (!Array.isArray(user.permissions)) return true;
  if (keys.length === 0) return true;
  return keys.some((k) => user.permissions!.includes(k));
}

/** Hook form: `const can = useCan(); if (can("wallet.withdraw")) …` */
export function useCan(): (...keys: string[]) => boolean {
  const user = useAuthStore((s) => s.user);
  return (...keys: string[]) => hasPermission(user, ...keys);
}
