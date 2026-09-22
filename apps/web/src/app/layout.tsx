import type { Metadata } from "next";
import "@fontsource-variable/geist";
import "./globals.css";
import "@/features/auth/account.css";
import "@/features/github/github.css";
import { AppShell } from "@/components/app-shell";
import { Providers } from "@/components/providers";

export const metadata: Metadata = {
  title: { default: "Forge · Engineering intelligence", template: "%s · Forge" },
  description: "Trace engineering delivery and build auditable pipeline automation.",
  robots: { index: false, follow: false },
  icons: { icon: "/forge.svg" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
