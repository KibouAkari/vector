import Link from "next/link";
import { ArrowLeft, Compass, MessageSquareText } from "lucide-react";

export default function NotFound() {
  return (
    <main className="vux-not-found">
      <div className="vux-not-found-glow" aria-hidden="true" />
      <div className="vux-not-found-panel">
        <span className="vux-not-found-kicker">VECTOR / UNKNOWN COORDINATES</span>
        <span className="vux-not-found-code" aria-hidden="true">404</span>
        <Compass className="vux-not-found-icon" size={32} strokeWidth={1.2} aria-hidden="true" />
        <h1>Looks like you took a wrong turn.</h1>
        <p>There is nothing at this address. Your workspace is still right where you left it.</p>
        <div className="vux-not-found-actions">
          <Link href="/"><ArrowLeft size={16} aria-hidden="true" /> Back to overview</Link>
          <Link href="/chat" className="vux-not-found-secondary"><MessageSquareText size={16} aria-hidden="true" /> Open chat</Link>
        </div>
      </div>
    </main>
  );
}
