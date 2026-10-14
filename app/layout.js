import "./globals.css";
import "./phase2.css";
import "./vector-v5.css";
import "./vector-v52.css";
import "./vector-v54.css";
import "./vector-v55.css";
import "./vector-v56.css";
import "./vector-v562.css";
import "./vector-v563.css";
import "./vector-v567.css";
import "./vector-v569.css";
import "./vector-v571.css";
import "./vector-v581.css";
import "./vector-interactions.css";
import "./vector-dashboard.css";
import "./vector-premium.css";
import "./vector-ui-585b.css";
import "./vector-chat-585c.css";
import "./vector-chat-585d.css";
import "./vector-ui-585e.css";
import "./vector-ui-585f.css";
import "./vector-workspace-ux.css";
import "./vector-chat-600.css";

import VectorRouteTransition from "../components/ui/vector-route-transition";

export const metadata = {
  title: {
    default: "Vector",
    template: "%s · Vector"
  },
  description: "Vector Personal AI Workspace",
  icons: {
    icon: [{ url: "/icon.svg?v=540", type: "image/svg+xml" }],
    shortcut: "/icon.svg?v=540",
    apple: "/apple-icon.svg?v=540"
  }
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        {children}
        <VectorRouteTransition />
      </body>
    </html>
  );
}
