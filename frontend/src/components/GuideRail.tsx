import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getJson } from "../services/api";
import { useTower } from "../store/useTower";
import type { Anomaly, Meta } from "../types";
import { emphasisFor, anchorAnomaly } from "../lib/locate";

const STEPS = [
  { path: "/", ask: "Something changed. Where does the chain look unhealthy?" },
  { path: "/detect", ask: "What moved against the previous window, and which signals left their baseline?" },
  { path: "/", ask: "This signal sits on a facility. What else is attached to it?" },
  { path: "/investigate", ask: "Who contributes the largest share of the gap? A share is not a cause." },
  { path: "/trace", ask: "Where did one affected order lose time?" },
];

export function GuideRail() {
  const step = useTower((state) => state.guideStep);
  const setGuideStep = useTower((state) => state.setGuideStep);
  const setFocus = useTower((state) => state.setFocus);
  const applyContext = useTower((state) => state.applyContext);
  const filters = useTower((state) => state.filters);
  const ready = useTower((state) => state.ready);
  const navigate = useNavigate();
  const anomalies = useQuery({
    queryKey: ["anomalies", filters],
    enabled: ready && step != null,
    queryFn: () => getJson<Anomaly[]>("/anomalies", filters),
  });
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => getJson<Meta>("/meta"), enabled: step != null });
  if (step == null) return null;
  const current = STEPS[Math.min(step, STEPS.length - 1)];

  function next() {
    const anchor = anchorAnomaly(anomalies.data ?? []);
    if (step === 0) {
      setGuideStep(1);
      navigate("/detect");
      return;
    }
    if (step === 1 && anchor) {
      setFocus({ kind: "anomaly", id: anchor.id }, emphasisFor(anchor));
      setGuideStep(2);
      navigate("/");
      return;
    }
    if (step === 2 && anchor) {
      applyContext(anchor.context.filters, anchor.context.metric, anchor.context.steps);
      setGuideStep(3);
      navigate("/investigate");
      return;
    }
    if (step === 3 && meta.data?.example_order_id) {
      setGuideStep(4);
      navigate(`/trace/${meta.data.example_order_id}`);
      return;
    }
    setGuideStep(null);
  }

  return (
    <div className="guide-rail">
      <p><span>Disruption {step + 1} / {STEPS.length}</span>{current.ask}</p>
      <div>
        <button className="text-btn" onClick={() => setGuideStep(null)}>Exit</button>
        <button className="text-btn primary" onClick={next}>{step >= STEPS.length - 1 ? "Done" : "Continue"}</button>
      </div>
    </div>
  );
}
