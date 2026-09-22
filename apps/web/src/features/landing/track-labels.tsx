import { integrations, ToolLogo } from "./integrations";

const checkpoints = [
  [80, 50],
  [280, 160],
  [120, 270],
  [280, 380],
];

export function TrackLabels({
  active,
  selected,
  onSelect,
}: {
  active: number;
  selected: number;
  onSelect: (source: number) => void;
}) {
  return (
    <div className="track-labels" aria-label="Illustrative delivery track">
      {integrations.map((tool, i) => (
        <button
          type="button"
          key={tool.id}
          className="track-stop"
          data-checkpoint={i}
          style={{ left: `${checkpoints[i][0] / 4}%`, top: `${checkpoints[i][1] / 4.7}%` }}
          aria-label={"Select " + tool.name + " checkpoint"}
          aria-pressed={selected === i}
          onClick={() => onSelect(i)}
        >
          <ToolLogo id={tool.id} />
          <span>
            <strong>{["GitHub", "Actions", "JUnit", "Sentry"][i]}</strong>
            <span>{["PR #184", "CI #928", "3 tests passed", "Release error"][i]}</span>
          </span>
        </button>
      ))}
      <div className="track-detail">
        {active < 2 && <span className="track-commit">commit 8f3a2c1</span>}
        {active === 2 && (
          <>
            <strong>Reproduce the failure</strong>
            <code>total(100, null)</code>
            <span>TypeError · regression run #929</span>
          </>
        )}
        {active === 3 && (
          <>
            <strong>Review the candidate fix</strong>
            <code>coupon?.percent ?? 0</code>
            <span>Verify with the failing test</span>
          </>
        )}
        {active === 4 && (
          <>
            <strong>Request a review</strong>
            <span>Commit + failed test attached</span>
            <span className="track-review">Human review required</span>
          </>
        )}
      </div>
    </div>
  );
}
