import type { Metadata } from "next";
import { RepositoriesPage } from "@/features/github/repositories-page";
export const metadata: Metadata = { title: "Repositories" };
export default function Page() {
  return <RepositoriesPage />;
}
