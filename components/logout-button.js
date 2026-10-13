"use client";

import {
  useRouter
} from "next/navigation";

export default function LogoutButton() {
  const router = useRouter();

  async function logout() {
    await fetch(
      "/api/auth/logout",
      {
        method: "POST"
      }
    );

    router.push("/login");
    router.refresh();
  }

  return (
    <button
      type="button"
      className="logout-button"
      onClick={logout}
    >
      Sign out
    </button>
  );
}
