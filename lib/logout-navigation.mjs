/**
 * Revoke the server session before navigating to a new document.
 * The caller supplies transport and navigation so ordering can be tested
 * without mounting a React component or contacting production services.
 */
export async function revokeSessionAndNavigate({ request, navigate }) {
  const response = await request("/api/auth/logout", {
    method: "POST",
    credentials: "same-origin",
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error("Sign out was not confirmed.");
  }

  navigate("/login");
}
