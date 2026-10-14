import "./model-intelligence.css";
import {
  requireFeature
} from "../../lib/auth";

import Sidebar
  from "../../components/sidebar";

import ModelsClient
  from "./models-client";


export const dynamic =
  "force-dynamic";


export default async function ModelsPage() {
  const session =
    await requireFeature("models");

  return (
    <div className="vector-shell">

      <Sidebar
        session={
          session
        }
      />

      <main className="main clean-main">

        <ModelsClient />

      </main>

    </div>
  );
}
