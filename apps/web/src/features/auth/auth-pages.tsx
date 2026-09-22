"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Anvil, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, errorMessage, safeReturn } from "@/lib/auth-client";
import type { Organization } from "@/lib/auth-types";
import { useAuth } from "./auth-provider";
import { Field, FormMessage } from "./form-parts";

function AuthFrame({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <main className="auth-page" id="main-content">
      <Link href="/" className="brand auth-brand" aria-label="Forge home">
        <Anvil size={23} strokeWidth={1.7} aria-hidden="true" />
        <span>Forge</span>
      </Link>
      <div className="auth-content">
        <noscript>
          <p className="form-error">Enable JavaScript to submit this secure form.</p>
        </noscript>
        <h1>{title}</h1>
        <p className="auth-description">{description}</p>
        {children}
      </div>
      <Link className="auth-home text-link" href="/">
        <ArrowLeft size={14} aria-hidden="true" />
        Back to Forge
      </Link>
    </main>
  );
}

export function CredentialsForm({
  mode,
  onComplete,
}: {
  mode: "login" | "register";
  onComplete?: () => void;
}) {
  const { authenticated } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const target = safeReturn(params.get("returnTo"));
  const registering = mode === "register";
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      await api(`/auth/${mode}`, {
        method: "POST",
        refresh: false,
        body: {
          email: String(form.get("email")).trim(),
          password: form.get("password"),
          ...(registering ? { name: String(form.get("name")).trim() } : {}),
        },
      });
      await authenticated();
      if (onComplete) onComplete();
      else router.replace(target);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="account-form" method="post" onSubmit={submit} aria-busy={busy}>
      {registering && (
        <Field
          label="Full name"
          name="name"
          autoComplete="name"
          required
          maxLength={100}
          disabled={busy}
        />
      )}
      <Field
        label="Email address"
        name="email"
        type="email"
        autoComplete="email"
        required
        maxLength={254}
        disabled={busy}
      />
      <Field
        label="Password"
        name="password"
        type="password"
        autoComplete={registering ? "new-password" : "current-password"}
        required
        minLength={registering ? 12 : undefined}
        maxLength={128}
        hint={
          registering
            ? "Use at least 12 characters. Spaces and password managers are welcome."
            : undefined
        }
        disabled={busy}
      />
      <FormMessage error={error} />
      <Button type="submit" disabled={busy}>
        {busy
          ? registering
            ? "Creating account..."
            : "Signing in..."
          : registering
            ? "Create account"
            : "Sign in"}
      </Button>
      {!registering && (
        <Link href="/forgot-password" className="text-link">
          Forgot your password?
        </Link>
      )}
    </form>
  );
}

export function CredentialsPage({ mode }: { mode: "login" | "register" }) {
  const params = useSearchParams();
  const registering = mode === "register";
  const target = safeReturn(params.get("returnTo"));
  return (
    <AuthFrame
      title={registering ? "Create your account" : "Sign in to Forge"}
      description={
        registering
          ? "Set up your account, then create an organization or join your team."
          : "Open your organization and continue your work."
      }
    >
      <CredentialsForm mode={mode} />
      <p className="auth-switch">
        {registering ? "Already have an account?" : "New to Forge?"}{" "}
        <Link
          href={`${registering ? "/login" : "/register"}?returnTo=${encodeURIComponent(target)}`}
        >
          {registering ? "Sign in" : "Create an account"}
        </Link>
      </p>
    </AuthFrame>
  );
}

export function RequestEmailForm({
  kind,
  email = "",
}: {
  kind: "verify-email" | "password-reset";
  email?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const reset = kind === "password-reset";
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSuccess("");
    const form = new FormData(event.currentTarget);
    try {
      await api(`/auth/${kind}/request`, {
        method: "POST",
        refresh: false,
        body: { email: String(form.get("email")).trim() },
      });
      setSuccess(
        reset
          ? "If this address has an account, a password reset link will be sent. Check your inbox and spam folder."
          : "If this address needs verification, a verification link will be sent. Check your inbox and spam folder.",
      );
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="account-form" method="post" onSubmit={submit} aria-busy={busy}>
      <Field
        label="Email address"
        name="email"
        type="email"
        autoComplete="email"
        defaultValue={email}
        required
        maxLength={254}
        disabled={busy}
      />
      <FormMessage error={error} success={success} />
      <Button type="submit" disabled={busy}>
        {busy ? "Sending..." : reset ? "Send reset link" : "Send verification link"}
      </Button>
    </form>
  );
}

export function ForgotPasswordPage() {
  return (
    <AuthFrame
      title="Reset your password"
      description="Enter your account email and we will send you a reset link."
    >
      <RequestEmailForm kind="password-reset" />
      <p className="auth-switch">
        <Link href="/login">Return to sign in</Link>
      </p>
    </AuthFrame>
  );
}

function useFragmentToken() {
  const [value, setValue] = useState<{ token: string; ready: boolean }>({
    token: "",
    ready: false,
  });
  const captured = useRef(false);
  useEffect(() => {
    if (captured.current) return;
    captured.current = true;
    const token = new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "";
    if (window.location.hash)
      window.history.replaceState(
        window.history.state,
        "",
        window.location.pathname + window.location.search,
      );
    // URL fragments are browser-only external state; never copy this one-time secret into storage.
    setValue({ token: token.length <= 2048 ? token : "", ready: true });
  }, []);
  return value;
}

export function ResetPasswordPage() {
  const { token, ready } = useFragmentToken();
  const { clearSession } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const password = String(form.get("password"));
    if (password !== form.get("confirm")) {
      setError("The passwords do not match. Enter the same password in both fields.");
      setBusy(false);
      return;
    }
    try {
      await api("/auth/password-reset/confirm", {
        method: "POST",
        refresh: false,
        body: { token, password },
      });
      await clearSession();
      setSuccess(true);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <AuthFrame
      title="Choose a new password"
      description="Your previous sessions will end when your password changes."
    >
      {!ready ? (
        <p role="status">Reading your reset link...</p>
      ) : success ? (
        <>
          <FormMessage success="Your password was changed. Sign in with your new password." />
          <Link className="text-link" href="/login">
            Sign in
          </Link>
        </>
      ) : !token ? (
        <>
          <FormMessage error="This reset link is missing its token. Request a new link to continue." />
          <Link className="text-link" href="/forgot-password">
            Request a new reset link
          </Link>
        </>
      ) : (
        <form className="account-form" method="post" onSubmit={submit} aria-busy={busy}>
          <Field
            label="New password"
            name="password"
            type="password"
            autoComplete="new-password"
            minLength={12}
            maxLength={128}
            required
            hint="Use at least 12 characters."
            disabled={busy}
          />
          <Field
            label="Confirm new password"
            name="confirm"
            type="password"
            autoComplete="new-password"
            minLength={12}
            maxLength={128}
            required
            disabled={busy}
          />
          <FormMessage error={error} />
          <Button type="submit" disabled={busy}>
            {busy ? "Changing password..." : "Change password"}
          </Button>
          <Link className="text-link" href="/forgot-password">
            Request a new reset link
          </Link>
        </form>
      )}
    </AuthFrame>
  );
}

export function VerifyEmailPage() {
  const { token, ready } = useFragmentToken();
  const { identity, reload } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  async function confirm() {
    setBusy(true);
    setError("");
    try {
      await api("/auth/verify-email/confirm", { method: "POST", refresh: false, body: { token } });
      setSuccess(true);
      await reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <AuthFrame
      title="Verify your email"
      description="Confirm your email address before accepting a team invitation."
    >
      {!ready ? (
        <p role="status">Reading your verification link...</p>
      ) : success || (!token && identity?.user.email_verified) ? (
        <>
          <FormMessage success="Your email address is verified." />
          <Link className="text-link" href="/app">
            Open your workspace
          </Link>
        </>
      ) : token ? (
        <div className="account-form">
          <FormMessage error={error} />
          <Button onClick={() => void confirm()} disabled={busy}>
            {busy ? "Verifying..." : "Verify email address"}
          </Button>
          {error && <RequestEmailForm kind="verify-email" email={identity?.user.email} />}
        </div>
      ) : (
        <RequestEmailForm kind="verify-email" email={identity?.user.email} />
      )}
    </AuthFrame>
  );
}

export function InvitePage() {
  const { token, ready } = useFragmentToken();
  const { identity, loading, error: sessionError, reload, selectOrganization } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [joined, setJoined] = useState<Organization | null>(null);
  async function accept() {
    setBusy(true);
    setError("");
    try {
      const org = await api<Organization>("/invitations/accept", {
        method: "POST",
        body: { token },
      });
      setJoined(org);
      await reload();
      await selectOrganization(org.id);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <AuthFrame
      title="Join your team"
      description="Use the verified email address your invitation was sent to."
    >
      {!ready || loading ? (
        <p role="status">Checking your invitation...</p>
      ) : !token ? (
        <FormMessage error="This invitation link is missing its token. Ask an organization administrator for a new invitation." />
      ) : joined ? (
        <>
          <FormMessage success={`You joined ${joined.name}.`} />
          <Link className="text-link" href="/app">
            Open your workspace
          </Link>
        </>
      ) : sessionError ? (
        <div className="account-form">
          <FormMessage error={sessionError.message} />
          <Button variant="outline" onClick={() => void reload()}>
            Try again
          </Button>
        </div>
      ) : !identity ? (
        <>
          <p className="invite-intro">
            {mode === "login"
              ? "Sign in to accept this invitation."
              : "Create an account with the invited email address."}
          </p>
          <CredentialsForm mode={mode} onComplete={() => void reload()} />
          <Button
            variant="ghost"
            className="auth-switch"
            onClick={() => setMode(mode === "login" ? "register" : "login")}
          >
            {mode === "login" ? "Create an account instead" : "Sign in instead"}
          </Button>
        </>
      ) : (
        <div className="account-form">
          <p>
            Signed in as <strong>{identity.user.email}</strong>.
          </p>
          {!identity.user.email_verified ? (
            <>
              <p>
                Verify this address using the email link, then return here to accept your
                invitation.
              </p>
              <RequestEmailForm kind="verify-email" email={identity.user.email} />
              <Button variant="outline" onClick={() => void reload()}>
                I have verified my email
              </Button>
            </>
          ) : (
            <>
              <FormMessage error={error} />
              <Button onClick={() => void accept()} disabled={busy}>
                {busy ? "Joining organization..." : "Accept invitation"}
              </Button>
            </>
          )}
        </div>
      )}
    </AuthFrame>
  );
}
