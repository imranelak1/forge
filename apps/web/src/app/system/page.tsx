import type { Metadata } from "next";
import { SystemStatus } from "@/features/system/system-status";

export const metadata: Metadata = { title: "System status" };

export default function SystemPage() {
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>System status</h1>
          <p>Inspect the services behind your Forge installation.</p>
        </div>
      </div>
      <SystemStatus />
      <section className="system-note">
        <h2>What these checks tell you</h2>
        <p>
          A healthy API is responding to requests. Database readiness also requires a working
          PostgreSQL connection and the current migration revision. These checks do not indicate
          that an engineering source is connected.
        </p>
      </section>
    </>
  );
}
