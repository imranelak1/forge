import { Check, GitPullRequest, ArrowUpRight } from "lucide-react";
import { integrations, ToolLogo } from "./integrations";

export function DeliveryRecords({
  active,
  selected,
  onSelect,
}: {
  active: number;
  selected: number;
  onSelect: (source: number) => void;
}) {
  const titles = [
    "PR #184 merged",
    "CI #928 passed",
    active >= 2 ? "Regression failed" : "3 tests passed",
    "Checkout error",
  ];
  const subtitles = [
    "PR #184 · 8f3a2c1",
    "GitHub Actions",
    active >= 2 ? "Reproduction · CI #929" : "Original test suite",
    "coupon is null",
  ];
  return (
    <div className="delivery-records" aria-label="Illustrative checkout delivery">
      {integrations.map((tool, i) => {
        const expanded =
          (active === -1 && i === 0) ||
          (active === 2 && i === 2) ||
          (active === 3 && (i === 0 || i === 3));
        return (
          <button
            key={tool.id}
            className="delivery-node"
            data-record={i}
            data-expanded={expanded}
            type="button"
            aria-label={"Select " + tool.name + " record"}
            aria-pressed={selected === i}
            onClick={() => onSelect(i)}
          >
            <div className="record-face">
              <div className="record-heading">
                <ToolLogo id={tool.id} />
                <span>{active === 4 ? ["Code", "Build", "Test", "Error"][i] : tool.short}</span>
                <span className="record-dot" />
              </div>
              {active !== 4 && (
                <>
                  <strong className="record-title">
                    {active === -1 && i === 0
                      ? "Handle coupon totals"
                      : active === 3 && i === 0
                        ? "Candidate fix"
                        : active >= 1 && active <= 3 && !expanded
                          ? [
                              "PR #184",
                              "CI #928",
                              active >= 2 ? "Failed test" : "3 passed",
                              "Sentry error",
                            ][i]
                          : titles[i]}
                  </strong>
                  <span className="record-meta">{subtitles[i]}</span>
                </>
              )}
              {expanded && (
                <div className="record-expanded" key={active}>
                  {i === 0 &&
                    (active === -1 ? (
                      <>
                        <span className="record-file">checkout.ts</span>
                        <code>
                          const discount =<br />
                          <span className="record-warning"> coupon.percent;</span>
                        </code>
                        <span className="record-foot">
                          <GitPullRequest size={12} /> Merged into main
                        </span>
                      </>
                    ) : (
                      <>
                        <span className="record-file">checkout.ts : 4</span>
                        <code>
                          <span className="record-deleted">− coupon.percent</span>
                          <br />
                          <span className="record-added">
                            + coupon?.percent
                            <br /> ?? 0
                          </span>
                        </code>
                        <span className="record-foot">Awaiting verification</span>
                      </>
                    ))}
                  {i === 2 && (
                    <>
                      <span className="record-file">checkout.test.ts</span>
                      <code>total(100, null)</code>
                      <div className="record-assertion">
                        <span>
                          Expected <b>100</b>
                        </span>
                        <span>
                          Received <b>TypeError</b>
                        </span>
                      </div>
                      <span className="record-foot">The missing case: no coupon</span>
                    </>
                  )}
                  {i === 3 && (
                    <>
                      <span className="record-file">TypeError</span>
                      <code>coupon is null</code>
                      <span className="record-stack">
                        total
                        <br />
                        checkout.ts : 4<br />
                        <br />
                        release
                        <br />
                        8f3a2c1
                      </span>
                    </>
                  )}
                </div>
              )}
            </div>
          </button>
        );
      })}
      <div className="delivery-node record-summary" data-record="4" data-expanded={active === 4}>
        <div className="record-face">
          {active === 0 && (
            <>
              <span className="record-file">Shared commit</span>
              <strong className="record-title">8f3a2c1</strong>
            </>
          )}
          {active === 1 && <span className="record-meta">Same commit. Linked evidence.</span>}
          {active === 2 && (
            <>
              <span className="record-file">Missing case</span>
              <strong className="record-title">No coupon</strong>
            </>
          )}
          {active === 3 && <span className="record-meta">Verify the candidate with CI #929</span>}
          {active === 4 && (
            <>
              <div className="record-heading">
                <ArrowUpRight size={17} />
                <span>Illustrative response</span>
              </div>
              <strong className="record-title">Request a review</strong>
              <div className="record-expanded">
                <p>The failing test and related change, ready for a human decision.</p>
                <ul>
                  <li>
                    <Check size={13} /> Commit 8f3a2c1 attached
                  </li>
                  <li>
                    <Check size={13} /> CI #929 failure attached
                  </li>
                </ul>
                <span className="record-review">Human review required</span>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
