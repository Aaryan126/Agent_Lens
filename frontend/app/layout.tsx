import "./globals.css";
import "@xyflow/react/dist/style.css";

export const metadata = {
  title: "AgentLens Ledger",
  description: "Session replay for agent decisions",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
