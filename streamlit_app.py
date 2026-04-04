from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from urllib import error, request

import streamlit as st
from graphviz import Digraph


REPO_ROOT = Path(__file__).resolve().parent
SAMPLE_TRACE_PATH = REPO_ROOT / "sample.json"
SAMPLE_LIVE_PATH = REPO_ROOT / "live_telemetry_sample.json"


def load_json(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def post_json(url: str, payload: str) -> dict:
    req = request.Request(
        url,
        data=payload.encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def safe_list(payload: dict, key: str) -> list:
    value = payload.get(key, [])
    return value if isinstance(value, list) else []


def render_card(title: str, body: str, meta: str | None = None, kind: str = "signal") -> None:
    meta_html = f'<div class="card-meta">{meta}</div>' if meta else ""
    st.markdown(
        f"""
        <div class="{kind}-card">
            <h4>{title}</h4>
            {meta_html}
            <div class="card-body">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def bullet_lines(items: list[str]) -> str:
    return "".join(f"<li>{item}</li>" for item in items)


def metric_card(label: str, value: str, tone: str = "neutral") -> None:
    st.markdown(
        f"""
        <div class="metric-card {tone}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@contextmanager
def section(title: str):
    with st.container(border=True):
        st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
        yield


def format_percent(value: float) -> str:
    return f"{int(value * 100)}%"


def graph_query_url(analyze_url: str) -> str:
    if "/analyze" in analyze_url:
        return analyze_url.replace("/analyze", "/graph-query")
    return analyze_url.rstrip("/") + "/graph-query"


def key_signal_summary(request_payload: dict) -> tuple[str, str, str]:
    logs = len(safe_list(request_payload, "logs"))
    metrics = len(safe_list(request_payload, "metrics"))
    alerts = len(safe_list(request_payload, "alerts"))
    return str(logs), str(metrics), str(alerts)


def build_graphviz(neighborhood: dict, trace_analysis: dict, trace: dict) -> Digraph:
    graph = Digraph()
    graph.attr(rankdir="LR", bgcolor="transparent", pad="0.2", nodesep="0.45", ranksep="0.7")
    graph.attr("node", shape="box", style="rounded,filled", fontname="Helvetica", color="#d7dee8")
    graph.attr("edge", color="#64748b", penwidth="1.4")

    failure_point = trace_analysis.get("failure_point", "")
    root_service = trace.get("root_service", "")
    blast_services = set(neighborhood.get("affected_services", []))

    services: set[str] = set()
    for rel in neighborhood.get("relationships", []):
        source = rel.get("source")
        target = rel.get("target")
        if source:
            services.add(source)
        if target:
            services.add(target)
    if root_service:
        services.add(root_service)
    if failure_point:
        services.add(failure_point)

    for service in services:
        fill = "#fffaf4"
        font = "#102239"
        if service == failure_point:
            fill = "#b23a21"
            font = "#fff7f2"
        elif service == root_service:
            fill = "#183354"
            font = "#f5efe6"
        elif service in blast_services:
            fill = "#f4d7c8"
        graph.node(service, service, fillcolor=fill, fontcolor=font)

    for rel in neighborhood.get("relationships", []):
        source = rel.get("source")
        target = rel.get("target")
        if source and target:
            graph.edge(source, target)

    return graph


st.set_page_config(
    page_title="RocketRide Incident Console",
    page_icon="RR",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --ink: #102239;
        --paper: rgba(255,255,255,0.92);
        --accent: #c24d2c;
        --accent-soft: rgba(194, 77, 44, 0.14);
        --muted: #5f6b7a;
        --line: rgba(16,34,57,0.10);
    }
    .stApp {
        background:
            radial-gradient(circle at top left, rgba(243, 110, 68, 0.18), transparent 28%),
            radial-gradient(circle at top right, rgba(15, 91, 206, 0.22), transparent 30%),
            linear-gradient(180deg, #07111f 0%, #09192b 44%, #f4efe6 44%, #f4efe6 100%);
    }
    .hero {
        padding: 1.4rem 1.6rem;
        border-radius: 24px;
        background: linear-gradient(135deg, rgba(7,17,31,0.92), rgba(16,34,57,0.86));
        border: 1px solid rgba(255,255,255,0.08);
        color: #f4efe6;
        box-shadow: 0 18px 50px rgba(4, 10, 20, 0.28);
        margin-bottom: 1rem;
    }
    .hero h1 { margin: 0; font-size: 2.25rem; letter-spacing: -0.04em; }
    .hero p { margin: 0.55rem 0 0 0; color: #c7d5e8; font-size: 1rem; max-width: 60rem; }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(7,17,31,0.96), rgba(16,34,57,0.96));
    }
    [data-testid="stSidebar"] * {
        color: #f5efe6;
    }
    .sidebar-note {
        background: rgba(255,255,255,0.08);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px;
        padding: 0.85rem 0.9rem;
        margin-bottom: 0.9rem;
    }
    .sidebar-note strong {
        display: block;
        margin-bottom: 0.35rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-size: 0.78rem;
    }
    .metric-card {
        border-radius: 20px;
        padding: 1rem 1.1rem;
        margin-bottom: 0.75rem;
        color: #f8f1e6;
        min-height: 110px;
        box-shadow: 0 14px 30px rgba(7,17,31,0.18);
    }
    .metric-card.neutral { background: linear-gradient(160deg, #102239, #183354); }
    .metric-card.alert { background: linear-gradient(160deg, #6f1d1b, #b23a21); }
    .metric-card.good { background: linear-gradient(160deg, #134e4a, #1b7b72); }
    .metric-label { font-size: 0.84rem; text-transform: uppercase; letter-spacing: 0.08em; opacity: 0.82; }
    .metric-value { font-size: 1.8rem; margin-top: 0.45rem; font-weight: 700; letter-spacing: -0.04em; }
    .section-title {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--accent);
        margin-bottom: 0.8rem;
        font-weight: 700;
    }
    .summary-text { font-size: 1.12rem; line-height: 1.7; color: var(--ink); }
    .impact-chip {
        display: inline-block;
        padding: 0.36rem 0.72rem;
        margin: 0.24rem 0.35rem 0 0;
        border-radius: 999px;
        background: var(--ink);
        color: #f4efe6;
        font-size: 0.86rem;
    }
    .service-card, .signal-card {
        background: linear-gradient(180deg, #fffaf4, #fff);
        border: 1px solid var(--accent-soft);
        border-radius: 18px;
        padding: 1rem 1.05rem;
        margin-bottom: 0.85rem;
    }
    .service-card h4, .signal-card h4 { margin: 0; color: var(--ink); font-size: 1rem; }
    .card-meta { margin-top: 0.25rem; color: var(--muted); font-size: 0.84rem; }
    .card-body { margin-top: 0.55rem; color: #334155; line-height: 1.55; }
    .card-body p { margin: 0.2rem 0 0.55rem 0; }
    .card-body ul { margin: 0.3rem 0 0 1rem; padding: 0; }
    .timeline-row {
        border-left: 3px solid var(--accent);
        padding: 0.2rem 0 1rem 1rem;
        margin-left: 0.4rem;
        margin-bottom: 0.35rem;
    }
    .timeline-row strong { color: var(--ink); }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--paper);
        border-radius: 22px;
        box-shadow: 0 10px 28px rgba(31, 41, 55, 0.08);
        border: 1px solid var(--line);
    }
    div[data-testid="stVerticalBlockBorderWrapper"] > div {
        padding: 0.45rem 0.45rem 0.35rem 0.45rem;
    }
    button[kind="primary"] {
        border-radius: 999px;
        background: linear-gradient(160deg, #c24d2c, #e87840);
        border: 0;
    }
    div[data-baseweb="tab-list"] {
        gap: 0.4rem;
    }
    button[data-baseweb="tab"] {
        border-radius: 999px;
        background: rgba(255,255,255,0.7);
        border: 1px solid rgba(16,34,57,0.08);
        padding: 0.35rem 0.9rem;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background: #102239;
        color: #f4efe6;
    }
    .stTabs [data-baseweb="tab-panel"] {
        padding-top: 1rem;
    }
    .status-banner {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.85rem 1rem;
        margin-bottom: 1rem;
        background: rgba(255,255,255,0.14);
        border: 1px solid rgba(255,255,255,0.14);
        border-radius: 18px;
        color: #eef4ff;
    }
    .status-banner strong { display: block; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.08em; }
    .status-banner span { font-size: 1rem; color: #d6e1f2; }
    .overview-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.75rem;
        margin-top: 0.5rem;
    }
    .overview-pill {
        background: rgba(16,34,57,0.05);
        border: 1px solid rgba(16,34,57,0.08);
        border-radius: 16px;
        padding: 0.8rem 0.9rem;
    }
    .overview-pill strong {
        display: block;
        font-size: 0.78rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted);
    }
    .overview-pill span {
        display: block;
        margin-top: 0.25rem;
        font-size: 1.1rem;
        color: var(--ink);
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
        <h1>RocketRide Incident Console</h1>
        <p>An operator cockpit for natural-language reasoning, trace progression, telemetry signals, and graph-aware blast-radius analysis.</p>
        <div class="status-banner">
            <div>
                <strong>Operating Modes</strong>
                <span>Trace analysis, live telemetry normalization, graph-aware impact mapping</span>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Control Panel")
    st.markdown(
        """
        <div class="sidebar-note">
            <strong>How To Use</strong>
            Paste a trace or live telemetry payload, run analysis, then move through the tabs from overview to graph evidence.
        </div>
        """,
        unsafe_allow_html=True,
    )
    backend_url = st.text_input("Backend analyze URL", "http://localhost:8010/analyze")
    live_backend_url = st.text_input("Live telemetry URL", "http://localhost:8010/telemetry/analyze")
    payload_mode = st.radio("Payload source", ["Trace payload", "Live telemetry"], index=0)
    selected_path = SAMPLE_TRACE_PATH if payload_mode == "Trace payload" else SAMPLE_LIVE_PATH
    default_url = backend_url if payload_mode == "Trace payload" else live_backend_url
    uploaded_file = st.file_uploader("Optional JSON upload", type=["json"])
    payload_text = st.text_area(
        "JSON payload",
        uploaded_file.getvalue().decode("utf-8") if uploaded_file else load_json(selected_path),
        height=360,
    )
    analyze_clicked = st.button("Run RocketRide Analysis", use_container_width=True)

result: dict | None = None
request_payload: dict | None = None
graph_view: dict | None = None
error_message: str | None = None

if analyze_clicked:
    try:
        request_payload = json.loads(payload_text)
        result = post_json(default_url, payload_text)
        failure_point = result.get("trace_analysis", {}).get("failure_point")
        if failure_point:
            try:
                graph_view = post_json(graph_query_url(backend_url), json.dumps({"service_name": failure_point}))
            except Exception:
                graph_view = None
    except json.JSONDecodeError as exc:
        error_message = f"Payload is not valid JSON: {exc}"
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        error_message = f"Backend returned HTTP {exc.code}: {details}"
    except error.URLError as exc:
        error_message = (
            f"Could not reach RocketRide at {default_url}. "
            f"Start the backend first, then try again. Details: {exc.reason}"
        )
    except Exception as exc:
        error_message = f"Unexpected error: {exc}"

if error_message:
    st.error(error_message)

if result and request_payload:
    narrative = result.get("narrative", {})
    impact = result.get("impact_analysis", {})
    trace = result.get("structured_trace", {})
    trace_analysis = result.get("trace_analysis", {})
    graph = result.get("graph_result", {})
    incidents = safe_list(result, "incident_matches")
    spans = safe_list(trace, "raw_spans") or safe_list(request_payload, "spans")
    logs = safe_list(request_payload, "logs")
    metrics = safe_list(request_payload, "metrics")
    alerts = safe_list(request_payload, "alerts")
    errors = safe_list(request_payload, "errors")
    deployments = safe_list(request_payload, "deployments")
    hosts = safe_list(request_payload, "host_signals")
    log_count, metric_count, alert_count = key_signal_summary(request_payload)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Severity", str(impact.get("severity", "unknown")).upper(), "alert")
    with c2:
        metric_card("Failure Point", trace_analysis.get("failure_point", "unknown"))
    with c3:
        metric_card("Affected Services", str(len(impact.get("blast_radius", []))), "neutral")
    with c4:
        metric_card("Confidence", format_percent(float(result.get("confidence_score", 0))), "good")

    tabs = st.tabs(
        [
            "Overview",
            "Trace Timeline",
            "Signals",
            "Deployments & Hosts",
            "Similar Incidents",
            "Graph Explorer",
            "Raw Data",
        ]
    )

    with tabs[0]:
        left, right = st.columns([1.25, 0.95])
        with left:
            with section("Executive Summary"):
                st.markdown(
                    f'<div class="summary-text">{narrative.get("executive_summary", result.get("root_cause", ""))}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"""
                    <div class="overview-grid">
                        <div class="overview-pill">
                            <strong>Failure Point</strong>
                            <span>{trace_analysis.get("failure_point", "unknown")}</span>
                        </div>
                        <div class="overview-pill">
                            <strong>Root Service</strong>
                            <span>{trace.get("root_service", "unknown")}</span>
                        </div>
                        <div class="overview-pill">
                            <strong>Severity</strong>
                            <span>{str(impact.get("severity", "unknown")).upper()}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with section("Affected Services"):
                st.write(narrative.get("affected_services_overview", ""))
                for service in impact.get("blast_radius", []):
                    st.markdown(f'<span class="impact-chip">{service}</span>', unsafe_allow_html=True)

            with section("Cause Chain"):
                for step in narrative.get("likely_cause_chain", []):
                    st.write(f"- {step}")

            with section("Service Impact Cards"):
                for item in narrative.get("service_impacts", []):
                    render_card(
                        item.get("service", "unknown-service"),
                        f"<p>{item.get('impact', '')}</p><ul>{bullet_lines(item.get('evidence', []))}</ul>",
                        meta="Impact assessment",
                        kind="service",
                    )

        with right:
            with section("Likely Root Cause"):
                st.write(result.get("root_cause", ""))

            with section("Recommended Actions"):
                for action in narrative.get("recommended_actions", result.get("solutions", [])):
                    st.write(f"- {action}")

            with section("Telemetry Footprint"):
                st.write(f"Trace ID: `{trace.get('trace_id', 'n/a')}`")
                st.write(f"Provider: `{trace.get('provider', 'n/a')}`")
                st.write(f"Entry point: `{trace.get('root_service', 'n/a')}` on `{trace.get('root_endpoint', 'n/a')}`")
                st.write(f"Error type: `{trace.get('error_type', 'n/a')}`")
                st.write(f"Latency: `{trace.get('latency_ms', 0)} ms`")
                st.markdown(
                    f"""
                    <div class="overview-grid">
                        <div class="overview-pill">
                            <strong>Logs</strong>
                            <span>{log_count}</span>
                        </div>
                        <div class="overview-pill">
                            <strong>Metrics</strong>
                            <span>{metric_count}</span>
                        </div>
                        <div class="overview-pill">
                            <strong>Alerts</strong>
                            <span>{alert_count}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with section("Dependency Path"):
                for rel in graph.get("relationships", []):
                    st.write(f"- {rel.get('source')} -> {rel.get('target')}")

    with tabs[1]:
        with section("Trace Timeline"):
            if spans:
                ordered_spans = sorted(spans, key=lambda item: (item.get("parent_id") is not None, item.get("duration_ms", 0)), reverse=False)
                for span in ordered_spans:
                    status = str(span.get("status", "ok")).upper()
                    error_type = span.get("error_type") or "None"
                    st.markdown(
                        f"""
                        <div class="timeline-row">
                            <strong>{span.get("service", "unknown-service")}</strong> · {span.get("operation", span.get("name", "operation"))}<br/>
                            Status: <code>{status}</code> | Duration: <code>{span.get("duration_ms", span.get("durationMs", 0))} ms</code> | Error: <code>{error_type}</code>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.info("No span timeline found in the current payload.")

        with section("Trace Analysis"):
            st.write(trace_analysis.get("summary", ""))
            for hypothesis in trace_analysis.get("suspected_issues", []):
                st.write(f"- {hypothesis}")

    with tabs[2]:
        signal_tabs = st.tabs(["Logs", "Metrics", "Alerts", "Errors"])

        with signal_tabs[0]:
            with section("Log Records"):
                if logs:
                    for log in logs:
                        render_card(
                            f'{log.get("service", log.get("serviceName", "unknown-service"))} · {log.get("level", "INFO")}',
                            f"<p>{log.get('message', '')}</p><p><code>{log.get('timestamp', '')}</code></p>",
                            meta=log.get("logger"),
                        )
                else:
                    st.info("No logs were present in the payload.")

        with signal_tabs[1]:
            with section("Metrics"):
                if metrics:
                    for metric in metrics:
                        render_card(
                            f'{metric.get("service", metric.get("serviceName", "unknown-service"))} · {metric.get("name", "")}',
                            f"<p>Value: <strong>{metric.get('value', '')} {metric.get('unit', '')}</strong></p><p>Aggregation: <code>{metric.get('aggregation', 'n/a')}</code></p>",
                            meta=metric.get("source", "telemetry metric"),
                        )
                else:
                    st.info("No metrics were present in the payload.")

        with signal_tabs[2]:
            with section("Alerts"):
                if alerts:
                    for alert_item in alerts:
                        render_card(
                            f'{alert_item.get("service", alert_item.get("serviceName", "unknown-service"))} · {alert_item.get("name", "")}',
                            f"<p>{alert_item.get('description', '')}</p><p>Severity: <code>{alert_item.get('severity', '')}</code> | State: <code>{alert_item.get('state', '')}</code></p>",
                            meta=alert_item.get("signal_type") or alert_item.get("source"),
                        )
                else:
                    st.info("No alerts were present in the payload.")

        with signal_tabs[3]:
            with section("Error Records"):
                if errors:
                    for err in errors:
                        render_card(
                            f'{err.get("service", "unknown-service")} · {err.get("error_class", "")}',
                            f"<p>{err.get('error_message', '')}</p><p>Count: <code>{err.get('count', 1)}</code> | Endpoint: <code>{err.get('endpoint', 'n/a')}</code></p>",
                            meta=err.get("timestamp"),
                        )
                else:
                    st.info("No discrete error records were present in the payload.")

    with tabs[3]:
        left, right = st.columns(2)
        with left:
            with section("Deployments"):
                if deployments:
                    for deployment in deployments:
                        render_card(
                            f'{deployment.get("service", "unknown-service")} · {deployment.get("version", "")}',
                            f"<p>{deployment.get('change_summary', '')}</p><p>Strategy: <code>{deployment.get('strategy', '')}</code> | Commit: <code>{deployment.get('commit_sha', '')}</code></p>",
                            meta=deployment.get("deployed_at"),
                        )
                else:
                    st.info("No deployment records were present in the payload.")

        with right:
            with section("Host Signals"):
                if hosts:
                    for host in hosts:
                        render_card(
                            f'{host.get("hostname", "")} · {host.get("service", "")}',
                            f"<p>CPU {host.get('cpu_pct', 0)}% | Memory {host.get('memory_pct', 0)}% | Disk {host.get('disk_pct', 0)}%</p><p>Status: <code>{host.get('node_status', '')}</code> | Restarts: <code>{host.get('pod_restarts', 0)}</code></p>",
                            meta=host.get("region"),
                        )
                else:
                    st.info("No host signals were present in the payload.")

    with tabs[4]:
        with section("Similar Incidents"):
            if incidents:
                for incident in incidents:
                    services = ", ".join(incident.get("services", []))
                    render_card(
                        f'{incident.get("incident_id", "")} · {incident.get("title", "")}',
                        f"<p>{incident.get('summary', '')}</p><p><strong>Root cause:</strong> {incident.get('root_cause', '')}</p><p><strong>Services:</strong> {services}</p><ul>{bullet_lines(incident.get('fix', []))}</ul>",
                        meta="Historical match",
                        kind="service",
                    )
            else:
                st.info("RocketRide did not return similar incidents for this payload.")

    with tabs[5]:
        left, right = st.columns([1.05, 0.95])
        with left:
            with section("Graph Neighborhood"):
                neighborhood = graph_view or graph
                relationships = neighborhood.get("relationships", []) if isinstance(neighborhood, dict) else []
                if relationships:
                    st.graphviz_chart(build_graphviz(neighborhood, trace_analysis, trace), use_container_width=True)
                    st.divider()
                    for rel in relationships:
                        render_card(
                            f"{rel.get('source')} -> {rel.get('target')}",
                            "<p>Dependency or impact edge captured from graph analysis.</p>",
                            meta="Graph edge",
                        )
                else:
                    st.info("No graph neighborhood data is currently available.")

        with right:
            with section("Graph Query Details"):
                if neighborhood:
                    st.code(neighborhood.get("cypher", "No Cypher available"), language="cypher")
                    st.write("Affected services:")
                    for service in neighborhood.get("affected_services", []):
                        st.markdown(f'<span class="impact-chip">{service}</span>', unsafe_allow_html=True)
                else:
                    st.info("The graph query endpoint could not be reached.")

    with tabs[6]:
        raw_tabs = st.tabs(["Analysis Response", "Input Payload"])
        with raw_tabs[0]:
            with section("Analysis Response"):
                st.json(result)
        with raw_tabs[1]:
            with section("Input Payload"):
                st.json(request_payload)
