"use client";

import { useState } from "react";

/**
 * Force a new document after logout. A client-side route transition can
 * retain server-component payloads fetched for the previous account.
 */
export default function LogoutButton() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function logout() {
    if (pending) return;
    setPending(true);
    setError("");

    try {
      const response = await fetch("/api/auth/logout", {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store"
      });

      if (!response.ok) {
        throw new Error("Sign out was not confirmed.");
      }

      window.location.replace("/login");
    } catch {
      setError("Could not sign out. Please try again.");
      setPending(false);
    }
  }

  return (
    <>
      <button
        type="button"
        className="logout-button"
        onClick={logout}
        disabled={pending}
      >
        {pending ? "Signing out…" : "Sign out"}
      </button>
      {error && <span role="alert" className="vux-logout-error">{error}</span>}
    </>
  );
}
