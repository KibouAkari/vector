/**
 * Pure, fail-closed project permission decisions.
 * This module does not query the database or trust client-supplied roles.
 */
export function projectAccessAllowed({
  session,
  projectOwnerId,
  membershipRole,
  action = "read",
}) {
  if (!session?.userId) return false;
  if (!["read", "write", "manage"].includes(action)) return false;
  if (session.role === "owner") return true;
  if (session.features?.projects !== true) return false;
  if (projectOwnerId && projectOwnerId === session.userId) return true;
  if (action === "manage") return false;
  if (action === "write") return membershipRole === "editor";
  return membershipRole === "viewer" || membershipRole === "editor";
}
