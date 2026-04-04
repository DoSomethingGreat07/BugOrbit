import type { FinalAnalysisResponse } from "../types/api";

type InsightsPanelProps = {
  result: FinalAnalysisResponse;
};

export function InsightsPanel({ result }: InsightsPanelProps) {
  const narrative = result.narrative;
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Command Brief</p>
          <h2>Root cause, impact, and action plan</h2>
          <p className="panel-copy">
            A concise operational summary of what failed, how far it spread, and what the team should do next.
          </p>
        </div>
        <span className="severity-pill">{result.impact_analysis.severity}</span>
      </div>
      <div className="stats-grid">
        <article className="stat-card">
          <span>Failure point</span>
          <strong>{result.trace_analysis.failure_point}</strong>
        </article>
        <article className="stat-card">
          <span>Confidence</span>
          <strong>{Math.round(result.confidence_score * 100)}%</strong>
        </article>
        <article className="stat-card">
          <span>Affected services</span>
          <strong>{result.impact_analysis.blast_radius.length}</strong>
        </article>
      </div>
      {narrative ? (
        <div className="content-block emphasis-block">
          <h3>Executive summary</h3>
          <p>{narrative.executive_summary}</p>
        </div>
      ) : null}
      <div className="content-block">
        <h3>Root cause</h3>
        <p>{result.root_cause}</p>
      </div>
      {narrative ? (
        <div className="content-block">
          <h3>Blast radius overview</h3>
          <p>{narrative.affected_services_overview}</p>
        </div>
      ) : null}
      <div className="content-block">
        <h3>Suspected issues</h3>
        <ul>
          {result.trace_analysis.suspected_issues.map((issue) => (
            <li key={issue}>{issue}</li>
          ))}
        </ul>
      </div>
      {narrative ? (
        <div className="content-block">
          <h3>Likely cause chain</h3>
          <ul>
            {narrative.likely_cause_chain.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <div className="content-block">
        <h3>Response plan</h3>
        <ul>
          {(narrative?.recommended_actions ?? result.solutions).map((solution) => (
            <li key={solution}>{solution}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}
