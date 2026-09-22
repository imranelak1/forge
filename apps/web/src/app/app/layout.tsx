import { AuthBoundary } from "@/features/auth/auth-boundary";

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return <AuthBoundary>{children}</AuthBoundary>;
}
