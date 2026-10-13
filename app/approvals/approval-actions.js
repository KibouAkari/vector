"use client";

import {
  useRouter
} from "next/navigation";

export default function ApprovalActions({
  id
}) {
  const router =
    useRouter();

  async function decide(
    decision
  ) {
    await fetch(
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

    router.refresh();
  }

  return (
    <div className="approval-actions">

      <button
        className="control-button secondary"
        type="button"
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
