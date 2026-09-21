export const modules = [
  { id: "connect", label: "Connect", x: 104, y: 102, width: 104, height: 76, code: "INPUT / 01" },
  { id: "trace", label: "Trace", x: 386, y: 106, width: 110, height: 76, code: "LINK / 02" },
  {
    id: "understand",
    label: "Understand",
    x: 390,
    y: 380,
    width: 124,
    height: 78,
    code: "SENSE / 03",
  },
  {
    id: "investigate",
    label: "Investigate",
    x: 106,
    y: 400,
    width: 120,
    height: 78,
    code: "TRACE / 04",
  },
  { id: "automate", label: "Automate", x: 67, y: 245, width: 112, height: 76, code: "ACT / 05" },
] as const;

const routes = [
  "M156 178 V204 L216 264 H250",
  "M441 182 V210 L380 271 H366",
  "M452 380 V355 L410 313 H366",
  "M166 400 V370 L220 316 H250",
  "M179 283 H220 L250 299",
];

function Pins({
  x,
  y,
  width,
  height,
  count = 8,
}: {
  x: number;
  y: number;
  width: number;
  height: number;
  count?: number;
}) {
  return (
    <g fill="url(#pin-metal)">
      {Array.from({ length: count }, (_, i) => {
        const horizontal = x + 10 + (i * (width - 20)) / (count - 1);
        const vertical = y + 10 + (i * (height - 20)) / (count - 1);
        return (
          <g key={i}>
            <rect x={horizontal} y={y - 9} width="4" height="10" rx="1" />
            <rect x={horizontal} y={y + height - 1} width="4" height="10" rx="1" />
            <rect x={x - 9} y={vertical} width="10" height="4" rx="1" />
            <rect x={x + width - 1} y={vertical} width="10" height="4" rx="1" />
          </g>
        );
      })}
    </g>
  );
}

function ModuleSymbol({ index, x, y }: { index: number; x: number; y: number }) {
  return (
    <g
      transform={`translate(${x} ${y})`}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {index === 0 && (
        <>
          <path d="M0 5 H8 L15 12 H29 M0 19 H8 L15 12" />
          <circle cx="0" cy="5" r="2.5" />
          <circle cx="0" cy="19" r="2.5" />
          <rect x="29" y="8" width="8" height="8" rx="1" />
        </>
      )}
      {index === 1 && (
        <>
          <path d="M3 3 V21 M3 9 C3 17 30 9 30 19" />
          <circle cx="3" cy="3" r="3" />
          <circle cx="3" cy="24" r="3" />
          <circle cx="30" cy="22" r="3" />
        </>
      )}
      {index === 2 && (
        <>
          <path d="M0 25 V17 H7 V7 H14 V20 H21 V0 H28 V25" />
          <path d="M-3 29 H34" opacity=".4" />
        </>
      )}
      {index === 3 && (
        <>
          <circle cx="12" cy="11" r="10" />
          <path d="m20 19 10 10 M8 11 H16 M12 7 V15" />
        </>
      )}
      {index === 4 && (
        <>
          <path d="m14 0-12 16 H14 L10 30 31 10 H19 L23 0 Z" />
        </>
      )}
    </g>
  );
}

export function CircuitBoard() {
  return (
    <svg className="circuit-svg" viewBox="0 0 600 610" fill="none" aria-hidden="true">
      <defs>
        <linearGradient
          id="board-surface"
          x1="75"
          y1="50"
          x2="490"
          y2="530"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#292a29" />
          <stop offset=".45" stopColor="#202120" />
          <stop offset="1" stopColor="#171917" />
        </linearGradient>
        <linearGradient id="chip-surface" x1="0" y1="0" x2="1" y2="1">
          <stop stopColor="#373936" />
          <stop offset=".5" stopColor="#252724" />
          <stop offset="1" stopColor="#1c1d1b" />
        </linearGradient>
        <linearGradient
          id="core-surface"
          x1="250"
          y1="243"
          x2="360"
          y2="340"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#d8c7a1" />
          <stop offset=".38" stopColor="#c0ab80" />
          <stop offset="1" stopColor="#8a7654" />
        </linearGradient>
        <linearGradient id="pin-metal">
          <stop stopColor="#5c6057" />
          <stop offset=".5" stopColor="#b5b7a7" />
          <stop offset="1" stopColor="#4f524a" />
        </linearGradient>
        <pattern id="pcb-grid" width="16" height="16" patternUnits="userSpaceOnUse">
          <circle cx="1" cy="1" r=".65" fill="#a4a891" opacity=".16" />
        </pattern>
      </defs>

      <path
        d="M72 48 H516 L550 82 V532 L526 556 H76 L48 528 V72 Z"
        fill="#0b0d0b"
        transform="translate(0 14)"
        stroke="#42473c"
      />
      <path
        d="M72 48 H516 L550 82 V532 L526 556 H76 L48 528 V72 Z"
        fill="url(#board-surface)"
        stroke="#5a5e51"
        strokeWidth="1.4"
      />
      <path
        d="M82 64 H510 L534 88 V523 L519 539 H83 L65 521 V82 Z"
        stroke="#71775f"
        strokeOpacity=".28"
      />
      <path d="M82 64 H510 L534 88 V523 L519 539 H83 L65 521 V82 Z" fill="url(#pcb-grid)" />

      <g stroke="#7d836c" strokeOpacity=".25" strokeWidth="1.2">
        {Array.from({ length: 8 }, (_, i) => (
          <path
            key={i}
            d={`M${83 + i * 8} 220 V${210 - i * 6} L${222 + i * 7} ${110 - i * 2} H350 V${140 + i * 7}`}
          />
        ))}
        {Array.from({ length: 7 }, (_, i) => (
          <path
            key={i}
            d={`M${255 + i * 8} 355 V${445 + i * 9} L${301 + i * 8} ${491 + i * 9} H${449 + i * 7}`}
          />
        ))}
        {Array.from({ length: 6 }, (_, i) => (
          <path
            key={i}
            d={`M365 ${238 + i * 9} H${471 + i * 7} L${491 + i * 7} ${218 + i * 9} V${199 - i * 8}`}
          />
        ))}
        <path d="M85 346 H158 L190 378 V390 M74 335 H178 L237 394 V505 H86 V487 M476 484 H507 V325 H536 M377 102 V79 H271 V222 M230 84 V180 L248 198 V223" />
      </g>

      <g fill="#383d32" stroke="#8c9279" strokeWidth="1">
        {[
          [81, 82],
          [514, 91],
          [81, 522],
          [515, 523],
        ].map(([x, y]) => (
          <g key={`${x}-${y}`}>
            <circle cx={x} cy={y} r="8" fill="#12150f" />
            <circle cx={x} cy={y} r="4" />
            <path d={`M${x - 3} ${y} H${x + 3}`} />
          </g>
        ))}
      </g>

      <g stroke="#484d3e" strokeWidth="2.5" strokeLinejoin="round">
        {routes.map((d, i) => (
          <path key={i} d={d} />
        ))}
        <path d="M226 439 H329 L390 418" />
        <path d="M496 145 H522 V340 L493 369" />
      </g>
      {routes.map((d, i) => (
        <g key={i} data-circuit={modules[i].id} className="circuit-route">
          <path
            className={`draw-trace trace-${i}`}
            d={d}
            pathLength="1"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinejoin="round"
          />
          <circle
            className={`route-node node-${i}`}
            cx={[156, 441, 452, 166, 179][i]}
            cy={[196, 196, 363, 385, 283][i]}
            r="3.5"
            fill="currentColor"
          />
        </g>
      ))}

      <g className="circuit-passives">
        {[
          [268, 157],
          [290, 157],
          [312, 157],
          [334, 157],
          [293, 386],
          [315, 386],
          [337, 386],
          [443, 283],
          [443, 306],
          [100, 361],
          [125, 361],
        ].map(([x, y], i) => (
          <g key={i} transform={`translate(${x} ${y})`}>
            <rect width="13" height="22" rx="2" fill="#10130e" stroke="#434838" />
            <rect x="1" y="1" width="11" height="4" fill="url(#pin-metal)" />
            <rect x="1" y="17" width="11" height="4" fill="url(#pin-metal)" />
          </g>
        ))}
        {[
          [213, 191],
          [354, 199],
          [470, 330],
          [79, 398],
          [258, 471],
        ].map(([x, y], i) => (
          <g key={i}>
            <circle cx={x} cy={y + 3} r="8" fill="#0b0e09" />
            <circle cx={x} cy={y} r="8" fill="#555b48" stroke="#899173" />
            <path d={`M${x - 5} ${y} H${x + 5}`} stroke="#272e20" />
          </g>
        ))}
      </g>

      {modules.map((mod, i) => (
        <g key={mod.id}>
          <rect
            x={mod.x - 4}
            y={mod.y - 4}
            width={mod.width + 8}
            height={mod.height + 8}
            rx="3"
            stroke="#a0a58b"
            strokeOpacity=".26"
            strokeDasharray="3 5"
          />
          <g className={`board-module module-${i}`} data-module={mod.id} data-circuit={mod.id}>
            <Pins x={mod.x} y={mod.y} width={mod.width} height={mod.height} count={6} />
            <rect
              x={mod.x}
              y={mod.y + 6}
              width={mod.width}
              height={mod.height}
              rx="3"
              fill="#0c0e0a"
            />
            <rect
              x={mod.x}
              y={mod.y}
              width={mod.width}
              height={mod.height}
              rx="3"
              fill="url(#chip-surface)"
              stroke="#6a705e"
            />
            <path
              d={`M${mod.x + 5} ${mod.y + mod.height - 6} V${mod.y + 5} H${mod.x + mod.width - 6}`}
              stroke="#969c86"
              strokeOpacity=".2"
            />
            <ModuleSymbol index={i} x={mod.x + 14} y={mod.y + 11} />
            <text
              x={mod.x + 14}
              y={mod.y + mod.height - 15}
              fill="#dbddd0"
              fontSize="12"
              fontWeight="500"
            >
              {mod.label}
            </text>
            <circle
              className="module-led"
              cx={mod.x + mod.width - 13}
              cy={mod.y + 14}
              r="2.5"
              fill="currentColor"
            />
          </g>
          <text
            x={mod.x}
            y={mod.y + mod.height + 25}
            fill="#8d947e"
            fontSize="7"
            fontFamily="monospace"
            letterSpacing="1"
          >
            {mod.code}
          </text>
        </g>
      ))}

      <g className="forge-core">
        <Pins x={250} y={239} width={116} height={112} count={12} />
        <rect x="245" y="240" width="126" height="123" rx="5" fill="#0a0c08" />
        <rect
          x="250"
          y="233"
          width="116"
          height="116"
          rx="4"
          fill="url(#core-surface)"
          stroke="#e0cba1"
          strokeWidth="1.3"
        />
        <rect x="258" y="241" width="100" height="100" rx="2" stroke="#655637" strokeOpacity=".6" />
        <path
          d="M299 258 H326 V265 H306 V276 H322 V283 H306 V300 H299 Z M287 258 H294 V300 H287 Z"
          fill="#302b21"
        />
        <text
          x="308"
          y="320"
          fill="#302b21"
          fontSize="15"
          fontWeight="650"
          textAnchor="middle"
          letterSpacing="-.4"
        >
          forge
        </text>
        <circle cx="260" cy="244" r="2" fill="#f4e0b6" />
      </g>

      <g fill="url(#pin-metal)">
        {Array.from({ length: 18 }, (_, i) => (
          <rect key={i} x={219 + i * 9} y="540" width="5" height="21" rx="1" />
        ))}
      </g>
      <text x="86" y="504" fill="#9ba18b" fontSize="8" letterSpacing="1.8">
        FORGE / ENGINEERING INTELLIGENCE
      </text>
      <text x="375" y="80" fill="#747d64" fontSize="7" letterSpacing="1">
        CONNECTED BY DESIGN
      </text>

      <path
        className="incident-path"
        d="M166 439 V370 L220 316 H308 V272 H380 L441 210 V144"
        pathLength="1"
        stroke="#ee8069"
        strokeWidth="2.5"
        strokeLinejoin="round"
      />
      <circle className="incident-signal" r="5" fill="#ffb5a3" stroke="#b24632" strokeWidth="3" />
    </svg>
  );
}
