import type { Metadata } from "next";
import { OrganizationSettings } from "@/features/organizations/organization-settings";

export const metadata: Metadata = { title: "Organization settings" };

export default function Page() {
  return <OrganizationSettings />;
}
