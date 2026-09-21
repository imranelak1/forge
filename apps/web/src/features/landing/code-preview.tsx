"use client";

import { useEffect, useRef, useState } from "react";
import { Check, Copy } from "lucide-react";

type Example = {
  file: string;
  language: string;
  code: string;
  highlight: number[];
  result: string;
  note: string;
};
const sources: Example[] = [
  {
    file: "pull_request.json",
    language: "JSON",
    code: '{\n  "action": "closed",\n  "number": 184,\n  "pull_request": {\n    "merged": true,\n    "head": { "sha": "8f3a2c1" }\n  }\n}',
    highlight: [3, 6],
    result: "PR #184 is linked to commit 8f3a2c1.",
    note: "GitHub webhook extract · SHA abbreviated",
  },
  {
    file: "workflow_run.json",
    language: "JSON",
    code: '{\n  "workflow_run": {\n    "run_number": 928,\n    "head_sha": "8f3a2c1",\n    "conclusion": "success"\n  }\n}',
    highlight: [3, 4],
    result: "CI run #928 tested the same change.",
    note: "GitHub Actions webhook extract · SHA abbreviated",
  },
  {
    file: "junit.xml",
    language: "XML",
    code: '<testsuite name="checkout"\n  tests="3" failures="0">\n  <testcase name="valid coupon" />\n  <testcase name="full price" />\n  <testcase name="free shipping" />\n</testsuite>',
    highlight: [1, 2],
    result: "The original CI report passed. The null-coupon case was missing.",
    note: "Sample JUnit report from run #928",
  },
  {
    file: "sentry-event.json",
    language: "JSON",
    code: '{\n  "release": "checkout@8f3a2c1",\n  "exception": {\n    "values": [{\n      "type": "TypeError",\n      "value": "coupon is null"\n    }]\n  }\n}',
    highlight: [2, 5, 6],
    result: "A production error points to that release.",
    note: "Sample Sentry event extract",
  },
];
const steps: Example[] = [
  sources[0],
  {
    file: ".github/workflows/ci.yml",
    language: "YAML",
    code: "name: Checkout CI\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - run: npm ci\n      - run: npm test",
    highlight: [7, 8, 9],
    result: "PR #184 → 8f3a2c1 → run #928 → checkout release.",
    note: "Example workflow · connected by commit, not timing",
  },
  {
    file: "checkout.test.ts",
    language: "TypeScript",
    code: 'import { expect, test } from "vitest";\nimport { total } from "./checkout";\n\ntest("checkout without a coupon", () => {\n  expect(total(100, null)).toBe(100);\n});\n\n// Before the fix:\n// TypeError: coupon is null',
    highlight: [4, 5, 9],
    result: "Reproduction run #929 exposes the missing null-coupon case.",
    note: "A developer-added regression test after the production error",
  },
  {
    file: "checkout.ts",
    language: "Diff",
    code: " export function total(price, coupon) {\n-  const percent = coupon.percent;\n+  const percent = coupon?.percent ?? 0;\n   return price * (1 - percent / 100);\n }",
    highlight: [2, 3],
    result: "The release points to this change. A null guard is a candidate fix to review.",
    note: "Illustrative investigation · a related change is not proof of cause",
  },
  {
    file: "review-rule.ts",
    language: "TypeScript",
    code: 'type Evidence = {\n  failures: number; commit: string;\n};\n\nexport function response(e: Evidence) {\n  if (e.failures === 0) return null;\n  return {\n    action: "request_review",\n    commit: e.commit\n  };\n}',
    highlight: [6, 8, 9],
    result:
      "A failed regression test requests review of the linked commit. A person decides what ships.",
    note: "Illustrative rule logic · not a published Forge API",
  },
];

function Tokens({ line }: { line: string }) {
  const tokens = line.split(
    /("[^"\n]*"|'[^'\n]*'|\b(?:export|function|return|const|if|type|import|from|null|true|false)\b|\b\d+\b|\/\/.*$)/g,
  );
  return tokens.map((token, i) => (
    <span
      key={i}
      className={
        token.startsWith("//")
          ? "syntax-comment"
          : /^["']/.test(token)
            ? "syntax-string"
            : /^\d+$/.test(token)
              ? "syntax-number"
              : /^(export|function|return|const|if|type|import|from|null|true|false)$/.test(token)
                ? "syntax-keyword"
                : undefined
      }
    >
      {token}
    </span>
  ));
}

export function CodePreview({ step, source }: { step: number; source: number }) {
  const example = step === 0 ? sources[source] : steps[step];
  const root = useRef<HTMLElement>(null);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">("idle");
  useEffect(() => {
    const element = root.current;
    if (!element) return;
    const preference = matchMedia("(prefers-reduced-motion: reduce)");
    let cancelled = false;
    let revert = () => {};
    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting) || preference.matches) return;
        observer.disconnect();
        void import("animejs").then(({ animate }) => {
          if (cancelled || preference.matches) return;
          const highlights = element.querySelectorAll(
            ".code-line.is-highlighted:not(.is-added):not(.is-removed)",
          );
          if (!highlights.length) return;
          const animation = animate(highlights, {
            backgroundColor: ["#4b4130", "#302e29"],
            duration: 380,
            ease: "out(3)",
          });
          revert = () => animation.revert();
        });
      },
      { threshold: 0.2 },
    );
    observer.observe(element);
    const stop = () => {
      if (preference.matches) revert();
    };
    preference.addEventListener("change", stop);
    return () => {
      cancelled = true;
      observer.disconnect();
      revert();
      preference.removeEventListener("change", stop);
    };
  }, [example]);
  useEffect(() => {
    if (copyState === "idle") return;
    const timer = setTimeout(() => setCopyState("idle"), 1800);
    return () => clearTimeout(timer);
  }, [copyState]);
  async function copy() {
    try {
      await navigator.clipboard.writeText(example.code);
      setCopyState("copied");
    } catch {
      setCopyState("error");
    }
  }
  return (
    <figure className="code-preview" ref={root} data-example={step}>
      <figcaption>
        <span>{example.file}</span>
        <span>{example.language}</span>
        <button type="button" onClick={() => void copy()} aria-label={"Copy " + example.file}>
          {copyState === "copied" ? (
            <Check size={14} aria-hidden="true" />
          ) : (
            <Copy size={14} aria-hidden="true" />
          )}
        </button>
      </figcaption>
      <pre tabIndex={0} aria-label={example.file + " example"}>
        <code>
          {example.code.split("\n").map((line, i) => (
            <span
              key={i}
              className={
                "code-line" +
                (example.highlight.includes(i + 1) ? " is-highlighted" : "") +
                (line.startsWith("+") ? " is-added" : line.startsWith("-") ? " is-removed" : "")
              }
            >
              <span className="line-number" aria-hidden="true">
                {i + 1}
              </span>
              <Tokens line={line} />
              {"\n"}
            </span>
          ))}
        </code>
      </pre>
      <div className="preview-result">
        <span>What this tells you</span>
        <p>{example.result}</p>
      </div>
      <p className="example-note">{example.note}</p>
      <span className="sr-only" role="status">
        {copyState === "copied"
          ? "Example copied"
          : copyState === "error"
            ? "Copy unavailable. Select the code to copy it."
            : ""}
      </span>
    </figure>
  );
}
