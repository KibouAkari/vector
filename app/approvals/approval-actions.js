"use client";
import {useState} from "react";

import {
  useRouter
} from "next/navigation";

export default function ApprovalActions({
  id
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const router =
    useRouter();

  async function decide(
    decision
  ) {
    if (pending) return;
    setPending(true); setError("");
    try {
    const response = await fetch(
      `/api/approvals/${id}/decision`,
      {
        method: "POST",

        headers: {
          "Content-Type":
            "application/json"
        },

        body:
          JSON.stringify({
            decision
          })
      }
    );

    if (!response.ok) throw new Error("The approval could not be saved. Reload and try again.");
    window.dispatchEvent(new Event('vector:approvals'));
    router.refresh();
    } catch (err) {setError(err.message);}
    finally {setPending(false); }
  }

  return (
    <div className="approval-actions">
      {error && <p role="alert">{error}</p>}

      <button
        className="control-button secondary"
        type="button"
        disabled={pending}
        onClick={
          () =>
            decide("approved")
        }
      >
        Approve
      </button>

      <button
        className="control-button danger"
        type="button"
        disabled={pending}
        onClick={
          () =>
            decide("rejected")
        }
      >
        Reject
      </button>

    </div>
  );
}
