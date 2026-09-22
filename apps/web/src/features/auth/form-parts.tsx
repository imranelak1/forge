"use client";

import { useId } from "react";

export function Field({
  label,
  hint,
  ...props
}: React.ComponentProps<"input"> & { label: string; hint?: string }) {
  const id = useId();
  return (
    <div className="form-field">
      <label htmlFor={id}>{label}</label>
      <input {...props} id={id} aria-describedby={hint ? `${id}-hint` : undefined} />
      {hint && (
        <p id={`${id}-hint`} className="field-hint">
          {hint}
        </p>
      )}
    </div>
  );
}

export function FormMessage({ error, success }: { error?: string; success?: string }) {
  if (error)
    return (
      <p className="form-error" role="alert">
        {error}
      </p>
    );
  if (success)
    return (
      <p className="form-success" role="status">
        {success}
      </p>
    );
  return null;
}
