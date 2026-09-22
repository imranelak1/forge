"use client";

import Image from "next/image";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/auth-client";
import {
  authorizationDestination,
  oauthErrorMessage,
  oauthProviders,
  providerNames,
  type Connection,
  type OAuthProvider,
  type ProviderAvailability,
} from "@/lib/oauth";
import { useAuth } from "./auth-provider";
import { FormMessage } from "./form-parts";

function ProviderLogo({ provider }: { provider: OAuthProvider }) {
  return provider === "github" ? (
    <Image
      className="provider-github-logo"
      src="/integrations/github.svg"
      width={20}
      height={20}
      alt=""
      aria-hidden="true"
    />
  ) : (
    <Image
      className="provider-google-logo"
      src="/integrations/google.png"
      width={20}
      height={20}
      alt=""
      aria-hidden="true"
    />
  );
}

function useProviders() {
  return useQuery({
    queryKey: ["auth", "providers"],
    queryFn: ({ signal }) =>
      api<ProviderAvailability>("/auth/providers", { signal, refresh: false }),
    staleTime: 60_000,
    retry: false,
  });
}

function useStartOAuth(
  intent: "login" | "link",
  returnTo: string,
  onBusyChange?: (value: boolean) => void,
) {
  const [busy, setBusy] = useState<OAuthProvider | null>(null);
  const [error, setError] = useState("");
  async function start(provider: OAuthProvider) {
    setBusy(provider);
    onBusyChange?.(true);
    setError("");
    try {
      const result = await api<{ authorization_url: string }>(`/auth/oauth/${provider}/start`, {
        method: "POST",
        refresh: intent === "link",
        body: { intent, return_to: returnTo },
      });
      window.location.assign(authorizationDestination(provider, result.authorization_url));
    } catch (err) {
      setError(errorMessage(err));
      setBusy(null);
      onBusyChange?.(false);
    }
  }
  return { busy, error, start };
}

export function SocialSignIn({
  returnTo,
  disabled = false,
  onBusyChange,
}: {
  returnTo: string;
  disabled?: boolean;
  onBusyChange?: (value: boolean) => void;
}) {
  const providers = useProviders();
  const { busy, error, start } = useStartOAuth("login", returnTo, onBusyChange);
  const unavailable = oauthProviders.filter(
    (provider) => !providers.data?.providers.some((item) => item.id === provider && item.enabled),
  );
  return (
    <div className="social-sign-in">
      <div
        className="provider-buttons"
        aria-label="Social sign-in"
        aria-busy={providers.isPending || !!busy}
      >
        {oauthProviders.map((provider) => (
          <Button
            type="button"
            variant="outline"
            className={`provider-button provider-button-${provider}`}
            key={provider}
            disabled={
              disabled ||
              !!busy ||
              providers.isPending ||
              providers.isError ||
              unavailable.includes(provider)
            }
            aria-describedby={
              unavailable.includes(provider) && providers.isSuccess
                ? "provider-availability"
                : undefined
            }
            onClick={() => void start(provider)}
          >
            <ProviderLogo provider={provider} />
            {busy === provider
              ? `Opening ${providerNames[provider]}...`
              : `Continue with ${providerNames[provider]}`}
          </Button>
        ))}
      </div>
      {providers.isPending && (
        <p className="field-hint" role="status">
          Checking sign-in options...
        </p>
      )}
      {providers.isError && (
        <div className="provider-recovery">
          <FormMessage error="Social sign-in options could not be loaded. Use your email or retry." />
          <Button variant="outline" onClick={() => void providers.refetch()}>
            Retry sign-in options
          </Button>
        </div>
      )}
      {providers.isSuccess && unavailable.length > 0 && (
        <p className="field-hint" id="provider-availability">
          {unavailable.length === 2
            ? "Social sign-in is not configured yet."
            : `${providerNames[unavailable[0]]} sign-in is not configured yet.`}
        </p>
      )}
      <FormMessage error={error} />
      <p className="auth-method-divider">or use your email</p>
    </div>
  );
}

export function ConnectedAccounts() {
  const params = useSearchParams();
  const { identity } = useAuth();
  const providers = useProviders();
  const connections = useQuery({
    queryKey: ["connections", identity?.user.id],
    queryFn: ({ signal }) => api<{ connections: Connection[] }>("/auth/connections", { signal }),
    enabled: !!identity,
    retry: false,
  });
  const { busy, error, start } = useStartOAuth("link", "/app/account");
  const callbackError = oauthErrorMessage(params.get("oauth_error"));
  const callbackSuccess =
    params.get("oauth") === "linked"
      ? "Account connected. You can use it to sign in to Forge."
      : "";
  return (
    <section className="settings-section" aria-labelledby="connections-title">
      <div className="settings-section-heading">
        <h2 id="connections-title">Connected accounts</h2>
        <p>Use GitHub or Google to sign in. This does not connect repositories or import data.</p>
      </div>
      <div className="connected-accounts">
        <FormMessage error={error || callbackError} success={callbackSuccess} />
        {!identity?.user.email_verified && (
          <p className="field-hint">Verify your Forge email before connecting an account.</p>
        )}
        {connections.isPending || providers.isPending ? (
          <p role="status">Loading connected accounts...</p>
        ) : connections.isError || providers.isError ? (
          <div className="provider-recovery">
            <FormMessage error="Connected accounts could not be loaded. Please try again." />
            <Button
              variant="outline"
              onClick={() => {
                void connections.refetch();
                void providers.refetch();
              }}
            >
              Retry connected accounts
            </Button>
          </div>
        ) : (
          <ul className="connection-list">
            {oauthProviders.map((provider) => {
              const connection = connections.data.connections.find(
                (item) => item.provider === provider,
              );
              const enabled = providers.data.providers.some(
                (item) => item.id === provider && item.enabled,
              );
              return (
                <li className="connection-row" key={provider}>
                  <div className="connection-identity">
                    <ProviderLogo provider={provider} />
                    <div>
                      <strong>{providerNames[provider]}</strong>
                      <p>
                        {connection
                          ? connection.email
                          : enabled
                            ? "Not connected"
                            : "Sign-in is not configured yet."}
                      </p>
                    </div>
                  </div>
                  {connection ? (
                    <span className="member-role">Connected</span>
                  ) : (
                    <Button
                      variant="outline"
                      disabled={!!busy || !enabled || !identity?.user.email_verified}
                      onClick={() => void start(provider)}
                    >
                      {busy === provider
                        ? `Opening ${providerNames[provider]}...`
                        : `Connect ${providerNames[provider]}`}
                    </Button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
