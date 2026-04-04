type GraphViewProps = {
  rootService: string;
  failurePoint?: string;
  affectedServices?: string[];
  relationships: Array<{ source: string; target: string }>;
};

export function GraphView({ rootService, failurePoint, affectedServices = [], relationships }: GraphViewProps) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Graph View</p>
          <h2>Dependency spread and impact path</h2>
          <p className="panel-copy">
            Follow the likely propagation chain from the customer-facing service into impacted dependencies.
          </p>
        </div>
      </div>
      <div className="chip-row">
        <span className="service-chip root-chip">Entry: {rootService}</span>
        {failurePoint ? <span className="service-chip failure-chip">Failure point: {failurePoint}</span> : null}
        {affectedServices.map((service) => (
          <span className="service-chip" key={service}>
            {service}
          </span>
        ))}
      </div>
      <div className="graph-list">
        <div className="graph-node root-node">{rootService}</div>
        {relationships.length === 0 ? (
          <p className="muted">No downstream dependencies were returned for this service.</p>
        ) : (
          relationships.map((edge) => (
            <div className="graph-edge" key={`${edge.source}-${edge.target}`}>
              <span className={`graph-node ${edge.source === failurePoint ? "failure-node" : ""}`}>{edge.source}</span>
              <span className="arrow">→</span>
              <span className={`graph-node accent-node ${edge.target === failurePoint ? "failure-node" : ""}`}>
                {edge.target}
              </span>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
