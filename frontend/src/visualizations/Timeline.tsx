import type { Journey, JourneyStage } from "../types";

export function JourneyTimeline({ journey }: { journey: Journey }) {
  const stages = journey.stages;
  if (!stages.length) return <p className="quiet">No timestamps on this order.</p>;
  const origin = stages.findIndex((stage) => stage.origin);
  const width = 960;
  const left = 36;
  const right = 24;
  const gap = (width - left - right) / Math.max(stages.length - 1, 1);
  const yPlan = 42;
  const yActual = 92;
  const point = (index: number) => left + index * gap;

  return (
    <svg viewBox={`0 0 ${width} 168`} width="100%" height="168" role="img" aria-label="Expected versus actual journey">
      <text x="8" y="16" fill="#8a97a3" fontSize="10">○ plan</text>
      <text x="62" y="16" fill="#0e7c6b" fontSize="10">● actual</text>
      <line x1={left} x2={width - right} y1={yPlan} y2={yPlan} stroke="#c5ced6" />
      {stages.map((stage, index) => {
        const x = point(index);
        const slipped = origin >= 0 && index >= origin;
        const y = slipped ? yActual : yPlan;
        const color = stage.origin || stage.added ? "#c4453c" : stage.propagated ? "#b86a12" : "#0e7c6b";
        const previous = index > 0 ? point(index - 1) : x;
        const previousSlipped = origin >= 0 && index - 1 >= origin;
        return (
          <g key={stage.key}>
            {index > 0 && (
              <line
                x1={previous}
                x2={x}
                y1={previousSlipped ? yActual : yPlan}
                y2={y}
                stroke={slipped ? color : "#0e7c6b"}
                strokeWidth={stage.origin ? 2.4 : 1.6}
              />
            )}
            <circle cx={x} cy={yPlan} r={5} fill="none" stroke="#8a97a3" />
            <circle cx={x} cy={y} r={stage.origin ? 7 : 5} fill={color} />
            {stage.origin && <text x={x} y={yActual - 16} textAnchor="middle" fill="#c4453c" fontSize="10">origin</text>}
            <text x={x} y="128" textAnchor="middle" fill="#1c2833" fontSize="11">{stage.label}</text>
            <text x={x} y="146" textAnchor="middle" fill="#5c6b78" fontSize="10">{caption(stage)}</text>
          </g>
        );
      })}
    </svg>
  );
}

function caption(stage: JourneyStage): string {
  if (stage.origin) return "delay starts";
  if (stage.added) return `+${(stage.own_delay_hours ?? 0).toFixed(0)}h`;
  if (stage.propagated) return "inherited";
  return "on plan";
}
