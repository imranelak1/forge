import { integrations, ToolLogo } from "./integrations";

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
      <span className="track-packet-label" aria-hidden="true">
        <span />
        8f3a2c1
      </span>
      <div className="track-detail" data-visible={active >= 2}>
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

export function TrackFallback() {
  return (
    <svg
      className="core-fallback"
      viewBox="0 0 500 420"
      fill="none"
      role="img"
      aria-label="Delivery track: GitHub pull request, Actions build, JUnit tests and Sentry release error. The error branches back to its related change for investigation and human review."
    >
      <path
        d="M155 40v35c0 55 190 10 190 65s-190 10-190 65 190 10 190 65-95 25-95 85"
        stroke="#77716a"
        strokeWidth="15"
      />
      <path
        d="M155 40v35c0 55 190 10 190 65s-190 10-190 65 190 10 190 65-95 25-95 85"
        stroke="#252423"
        strokeWidth="8"
      />
      <path
        d="M250 355C70 355 55 185 150 185M250 355C460 355 465 40 165 40"
        stroke="#85827e"
        strokeWidth="2"
        strokeDasharray="5 6"
      />
      {[
        [155, 52, "GitHub"],
        [345, 140, "Actions"],
        [155, 205, "JUnit"],
        [345, 270, "Sentry"],
      ].map(([x, y, label], i) => (
        <g key={label}>
          <rect
            x={Number(x) - 17}
            y={Number(y) - 9}
            width="34"
            height="18"
            rx="2"
            fill={["#ff4b4b", "#ffa828", "#b7ff54", "#05dbe9"][i]}
          />
          <text
            x={Number(x) + (i % 2 ? 32 : -32)}
            y={Number(y) + 6}
            textAnchor={i % 2 ? "start" : "end"}
            fill="#f6f4f2"
            fontFamily="sans-serif"
            fontSize="16"
          >
            {label}
          </text>
        </g>
      ))}
      <text
        x="250"
        y="395"
        textAnchor="middle"
        fill="#b4b1af"
        fontSize="14"
        fontFamily="sans-serif"
      >
        One commit. A connected delivery.
      </text>
    </svg>
  );
}
