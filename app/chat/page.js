import { requireSession } from "../../lib/auth";
import Sidebar from "../../components/sidebar";
import ChatClient from "./chat-client";

export const dynamic = "force-dynamic";

export default async function ChatPage() {
  const session = await requireSession();

  return (
    <div className="vector-shell">
      <Sidebar session={session} />

      <main className="main vector-chat-page">
        <ChatClient
          userId={session.userId}
          displayName={
            session.displayName ||
            session.username
          }
        />
      </main>
    </div>
  );
}
