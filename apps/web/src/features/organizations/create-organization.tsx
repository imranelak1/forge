"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/auth-client";
import type { Organization } from "@/lib/auth-types";
import { useAuth } from "@/features/auth/auth-provider";
import { Field, FormMessage } from "@/features/auth/form-parts";

export function CreateOrganization({ onboarding = false }: { onboarding?: boolean }) {
  const { reload, selectOrganization } = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const organization = await api<Organization>("/organizations", {
        method: "POST",
        body: { name: name.trim(), slug },
      });
      await reload();
      await selectOrganization(organization.id);
      router.replace("/app");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="organization-create account-section">
      <div>
        <h1>{onboarding ? "Create your organization" : "New organization"}</h1>
        <p>
          {onboarding
            ? "An organization keeps your team, permissions and engineering data together."
            : "Create a separate workspace with its own members and permissions."}
        </p>
      </div>
      <form className="account-form" method="post" onSubmit={submit} aria-busy={busy}>
        <Field
          label="Organization name"
          name="name"
          autoComplete="organization"
          required
          minLength={2}
          maxLength={100}
          value={name}
          disabled={busy}
          onChange={(event) => {
            const value = event.target.value;
            setName(value);
            if (!slugEdited)
              setSlug(
                value
                  .toLowerCase()
                  .replace(/[^a-z0-9]+/g, "-")
                  .replace(/^-+|-+$/g, "")
                  .slice(0, 63),
              );
          }}
        />
        <Field
          label="Organization slug"
          name="slug"
          autoComplete="off"
          spellCheck={false}
          required
          minLength={3}
          maxLength={63}
          pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
          value={slug}
          disabled={busy}
          hint="A unique identifier: 3 to 63 lowercase letters, numbers or hyphens."
          onChange={(event) => {
            setSlugEdited(true);
            setSlug(event.target.value);
          }}
        />
        <FormMessage error={error} />
        <Button type="submit" disabled={busy}>
          {busy ? "Creating organization..." : "Create organization"}
        </Button>
      </form>
      {onboarding ? (
        <p className="field-hint">
          Joining an existing team? Open the invitation link from your email. You can also manage
          your email verification in <Link href="/app/account">Account settings</Link>.
        </p>
      ) : (
        <Link className="text-link" href="/app">
          Cancel
        </Link>
      )}
    </section>
  );
}
