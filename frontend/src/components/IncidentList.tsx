import type { FinalAnalysisResponse } from "../types/api";

type IncidentListProps = {
  result: FinalAnalysisResponse;
};

export function IncidentList({ result }: IncidentListProps) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Historical Matches</p>
          <h2>Related incidents and prior fixes</h2>
          <p className="panel-copy">
            Use prior incidents to validate whether the current failure pattern looks familiar and worth reusing.
          </p>
        </div>
      </div>
      <div className="incident-list">
        {result.incident_matches.length === 0 ? (
          <p className="muted">No prior incidents matched this trace yet.</p>
        ) : (
          result.incident_matches.map((incident) => (
            <article className="incident-card" key={incident.incident_id}>
              <div className="incident-meta">{incident.incident_id}</div>
              <h3>{incident.title}</h3>
              <p>{incident.summary}</p>
              <p className="muted">{incident.services.join(" • ")}</p>
              <ul>
                {incident.fix.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ul>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
