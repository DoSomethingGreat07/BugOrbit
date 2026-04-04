import type { TraceRequest } from "../types/api";

type TraceInputProps = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  isLoading: boolean;
  exampleTrace: TraceRequest;
};

export function TraceInput({
  value,
  onChange,
  onSubmit,
  isLoading,
  exampleTrace
}: TraceInputProps) {
  return (
    <section className="panel panel-lg">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Trace Intake</p>
          <h2>Control Room Intake</h2>
          <p className="panel-copy">
            Paste production telemetry payloads, load the sample incident, and send them into RocketRide for
            root-cause reasoning and blast-radius analysis.
          </p>
        </div>
        <div className="button-row">
          <button className="secondary-button" onClick={() => onChange(JSON.stringify(exampleTrace, null, 2))}>
            Load sample
          </button>
          <button className="primary-button" onClick={onSubmit} disabled={isLoading}>
            {isLoading ? "Analyzing..." : "Run RocketRide"}
          </button>
        </div>
      </div>
      <textarea
        className="trace-input"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        spellCheck={false}
      />
    </section>
  );
}
