import type { Metadata } from "next";
import { CreateOrganization } from "@/features/organizations/create-organization";

export const metadata: Metadata = { title: "New organization" };

export default function Page() {
  return <CreateOrganization />;
}
