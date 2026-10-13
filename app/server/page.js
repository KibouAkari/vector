import {
  requireFeature
} from "../../lib/auth";

import Sidebar
  from "../../components/sidebar";

import ServerClient
  from "./server-client";

export const dynamic = "force-dynamic";

export default async function ServerPage() {
  const session =
    await requireFeature(
      "server"
    );

  return (
    <div className="vector-shell">

      <Sidebar
        session={
          session
        }
      />

      <main className="main clean-main">

        <ServerClient />

      </main>

    </div>
  );
}
