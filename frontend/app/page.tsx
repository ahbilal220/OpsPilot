"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

type User = { id: string; name: string; email: string; role: string };
type Service = {
  id: string;
  name: string;
  repository_url: string | null;
  default_branch: string;
  environment: string;
};
type Incident = {
  id: string;
  title: string;
  description: string;
  severity: "low" | "medium" | "high" | "critical";
  status: string;
  service_id: string | null;
  created_at: string;
};
type Investigation = {
  id: string;
  status: string;
  current_node: string;
  queue_task_id: string | null;
  iteration_count: number;
  tool_calls_count: number;
  llm_cost_usd: string;
  started_at: string | null;
  completed_at: string | null;
  state_snapshot: Record<string, unknown>;
};
type TimelineEvent = {
  id: string;
  event_type: string;
  actor_type: string;
  actor_id: string;
  payload: Record<string, unknown>;
  created_at: string;
};
type IncidentDetail = {
  incident: Incident;
  investigation: Investigation | null;
  timeline: TimelineEvent[];
  diagnosis: Diagnosis | null;
};
type Evidence = {
  id: string;
  type: string;
  source: string;
  source_reference: string | null;
  tool_name: string;
  content: string;
  summary: string;
  content_hash: string;
  observed_at: string | null;
  created_at: string;
};
type Hypothesis = {
  id: string;
  title: string;
  description: string;
  confidence: string;
  status: string;
  supporting_evidence_ids: string[];
  contradicting_evidence_ids: string[];
  validation_plan: string[];
  validation_result: Record<string, unknown>;
  created_at: string;
};
type Diagnosis = {
  id: string;
  root_cause: string;
  summary: string;
  confidence: string;
  evidence_ids: string[];
  limitations: string[];
  created_at: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.error?.message ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

function formatTime(value: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function Home() {
  const [user, setUser] = useState<User | null>(null);
  const [register, setRegister] = useState(false);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/v1/auth/me")
      .then(async response => {
        if (response.ok) setUser(await response.json());
        else if (response.status !== 401) {
          const body = await response.json().catch(() => null);
          setError(body?.error?.message ?? "Cannot reach the service.");
        }
      })
      .catch(() => setError("Cannot reach the service."))
      .finally(() => setBusy(false));
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const credentials = { email: form.get("email"), password: form.get("password") };
    try {
      if (register) {
        await request<User>("/api/v1/auth/register", {
          method: "POST",
          body: JSON.stringify({ ...credentials, name: form.get("name") }),
        });
      }
      setUser(
        await request<User>("/api/v1/auth/login", {
          method: "POST",
          body: JSON.stringify(credentials),
        }),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Sign in failed.");
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    setBusy(true);
    setError("");
    try {
      await request<{ message: string }>("/api/v1/auth/logout", { method: "POST" });
      setUser(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Sign out failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!user) {
    return (
      <main className="auth-shell">
        <header className="brand-bar">
          <span className="mark">O</span><strong>OpsPilot</strong><span className="badge">Phase 3</span>
        </header>
        <section className="auth-layout">
          <div className="intro">
            <p className="eyebrow">INCIDENT RESPONSE, WITH EVIDENCE</p>
            <h1>Move from alert<br />to investigation.</h1>
            <p>Register services, open incidents, and follow every investigation event from one operational record.</p>
          </div>
          <section className="card auth-card" aria-labelledby="auth-title">
            <p className="eyebrow">SECURE WORKSPACE</p>
            <h2 id="auth-title">{register ? "Create your account" : "Sign in"}</h2>
            <form onSubmit={submit}>
              {register && <label>Name<input name="name" autoComplete="name" required maxLength={120} /></label>}
              <label>Email<input name="email" type="email" autoComplete="email" required maxLength={320} /></label>
              <label>Password<input name="password" type="password" autoComplete={register ? "new-password" : "current-password"} required minLength={12} maxLength={128} /></label>
              <p className="hint">Use 12–128 characters.</p>
              <button disabled={busy}>{busy ? "Please wait…" : register ? "Create account & sign in" : "Sign in"}</button>
            </form>
            <button className="secondary" disabled={busy} onClick={() => { setRegister(!register); setError(""); }}>
              {register ? "Back to sign in" : "Create an account"}
            </button>
            {error && <p role="alert" className="error">{error}</p>}
          </section>
        </section>
        <footer>Evidence first. Human approval before external changes.</footer>
      </main>
    );
  }

  return <Dashboard user={user} onLogout={logout} busy={busy} />;
}

function Dashboard({ user, onLogout, busy }: { user: User; onLogout: () => void; busy: boolean }) {
  const [services, setServices] = useState<Service[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [detail, setDetail] = useState<IncidentDetail | null>(null);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([]);
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);
  const canWrite = user.role === "engineer" || user.role === "admin";

  const loadServices = useCallback(async () => setServices(await request<Service[]>("/api/v1/services")), []);
  const loadIncidents = useCallback(async () => setIncidents(await request<Incident[]>("/api/v1/incidents")), []);
  const loadDetail = useCallback(async (id: string) => setDetail(await request<IncidentDetail>(`/api/v1/incidents/${id}`)), []);
  const loadEvidence = useCallback(async (id: string) => setEvidence(await request<Evidence[]>(`/api/v1/incidents/${id}/evidence`)), []);
  const loadHypotheses = useCallback(async (id: string) => setHypotheses(await request<Hypothesis[]>(`/api/v1/incidents/${id}/hypotheses`)), []);
  const loadIncidentView = useCallback(async (id: string) => {
    await Promise.all([loadDetail(id), loadEvidence(id), loadHypotheses(id)]);
  }, [loadDetail, loadEvidence, loadHypotheses]);

  useEffect(() => {
    Promise.all([
      request<Service[]>("/api/v1/services"),
      request<Incident[]>("/api/v1/incidents"),
    ])
      .then(([nextServices, nextIncidents]) => {
        setServices(nextServices);
        setIncidents(nextIncidents);
      })
      .catch((cause: Error) => setError(cause.message));
  }, []);

  const selectedIncidentId = detail?.incident.id;
  useEffect(() => {
    if (!selectedIncidentId) return;
    const source = new EventSource(`/api/v1/incidents/${selectedIncidentId}/events`);
    const refresh = () => {
      loadIncidentView(selectedIncidentId).catch((cause: Error) => setError(cause.message));
      loadIncidents().catch((cause: Error) => setError(cause.message));
    };
    ["incident.created", "incident.updated", "investigation.queued", "investigation.started", "investigation.queue_failed", "incident.cancelled", "investigation.node_started", "triage.completed", "investigation.plan_created", "tool.started", "tool.completed", "tool.failed", "tool.policy_denied", "evidence.created", "hypothesis.created", "hypothesis.updated", "validation.completed", "diagnosis.ready", "investigation.inconclusive", "investigation.failed"].forEach(type => source.addEventListener(type, refresh));
    source.onerror = () => source.close();
    return () => source.close();
  }, [selectedIncidentId, loadIncidentView, loadIncidents]);

  async function act(action: () => Promise<void>) {
    setWorking(true);
    setError("");
    try { await action(); } catch (cause) { setError(cause instanceof Error ? cause.message : "Request failed."); }
    finally { setWorking(false); }
  }

  async function createService(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    await act(async () => {
      await request<Service>("/api/v1/services", {
        method: "POST",
        body: JSON.stringify({
          name: values.get("name"),
          repository_url: values.get("repository_url") || null,
          default_branch: values.get("default_branch"),
          environment: values.get("environment"),
        }),
      });
      form.reset();
      await loadServices();
    });
  }

  async function createIncident(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    await act(async () => {
      const incident = await request<Incident>("/api/v1/incidents", {
        method: "POST",
        body: JSON.stringify({
          title: values.get("title"),
          description: values.get("description"),
          severity: values.get("severity"),
          service_id: values.get("service_id") || null,
        }),
      });
      form.reset();
      await Promise.all([loadIncidents(), loadIncidentView(incident.id)]);
    });
  }

  async function investigate() {
    if (!detail) return;
    await act(async () => {
      await request(`/api/v1/incidents/${detail.incident.id}/investigate`, { method: "POST" });
      await Promise.all([loadIncidentView(detail.incident.id), loadIncidents()]);
    });
  }

  async function cancel() {
    if (!detail) return;
    await act(async () => {
      await request(`/api/v1/incidents/${detail.incident.id}/cancel`, { method: "POST" });
      await Promise.all([loadIncidentView(detail.incident.id), loadIncidents()]);
    });
  }

  const serviceNames = useMemo(() => new Map(services.map(service => [service.id, service.name])), [services]);
  const evidenceUsage = useMemo(() => {
    const usage = new Map<string, string[]>();
    for (const hypothesis of hypotheses) {
      for (const evidenceId of hypothesis.supporting_evidence_ids) {
        usage.set(evidenceId, [...(usage.get(evidenceId) ?? []), hypothesis.title]);
      }
    }
    return usage;
  }, [hypotheses]);

  return (
    <main className="dashboard-shell">
      <header className="brand-bar">
        <span className="mark">O</span><strong>OpsPilot</strong><span className="badge">Phase 3</span>
        <div className="identity"><span>{user.name}</span><small>{user.role}</small></div>
        <button className="quiet" disabled={busy} onClick={onLogout}>Sign out</button>
      </header>
      <section className="dashboard-heading">
        <div><p className="eyebrow">INCIDENT OPERATIONS</p><h1>Response workspace</h1></div>
        <div className="metric"><strong>{incidents.length}</strong><span>incidents</span></div>
        <div className="metric"><strong>{services.length}</strong><span>services</span></div>
      </section>
      {!canWrite && <div className="notice">Your viewer role has read-only access. An operator can grant the engineer role for incident actions.</div>}
      {error && <p role="alert" className="error error-banner">{error}</p>}

      <div className="workspace-grid">
        <aside className="stack">
          <section className="panel">
            <div className="panel-heading"><div><p className="eyebrow">REGISTRY</p><h2>Services</h2></div></div>
            {canWrite && <form className="compact-form" onSubmit={createService}>
              <label>Name<input name="name" placeholder="payments-api" required maxLength={120} /></label>
              <div className="form-row"><label>Environment<input name="environment" defaultValue="production" required /></label><label>Branch<input name="default_branch" defaultValue="main" required /></label></div>
              <label>Repository URL<input name="repository_url" type="url" placeholder="https://github.com/org/repo" /></label>
              <button disabled={working}>Add service</button>
            </form>}
            <ul className="service-list">
              {services.map(service => <li key={service.id}><span className="service-dot" /><div><strong>{service.name}</strong><small>{service.environment} · {service.default_branch}</small></div></li>)}
              {!services.length && <li className="empty">No services registered.</li>}
            </ul>
          </section>
          {canWrite && <section className="panel">
            <p className="eyebrow">NEW RECORD</p><h2>Open incident</h2>
            <form className="compact-form" onSubmit={createIncident}>
              <label>Title<input name="title" placeholder="Checkout latency increased" required maxLength={200} /></label>
              <label>Description<textarea name="description" placeholder="For the demo: p95 latency and database queries increased after the latest deployment." required maxLength={10000} /></label>
              <div className="form-row"><label>Severity<select name="severity" defaultValue="high"><option>low</option><option>medium</option><option>high</option><option>critical</option></select></label><label>Service<select name="service_id" defaultValue=""><option value="">Unassigned</option>{services.map(service => <option value={service.id} key={service.id}>{service.name}</option>)}</select></label></div>
              <button disabled={working}>Create incident</button>
            </form>
          </section>}
        </aside>

        <section className="panel incidents-panel">
          <div className="panel-heading"><div><p className="eyebrow">ACTIVE RECORDS</p><h2>Incidents</h2></div><button className="icon-button" onClick={() => loadIncidents().catch((cause: Error) => setError(cause.message))} aria-label="Refresh incidents">↻</button></div>
          <div className="incident-list">
            {incidents.map(incident => <button className={`incident-row ${detail?.incident.id === incident.id ? "selected" : ""}`} key={incident.id} onClick={() => loadIncidentView(incident.id).catch((cause: Error) => setError(cause.message))}>
              <span className={`severity severity-${incident.severity}`}>{incident.severity}</span>
              <span className="incident-summary"><strong>{incident.title}</strong><small>{serviceNames.get(incident.service_id ?? "") ?? "Unassigned"} · {formatTime(incident.created_at)}</small></span>
              <span className={`status status-${incident.status}`}>{incident.status.replaceAll("_", " ")}</span>
            </button>)}
            {!incidents.length && <div className="empty large-empty">No incidents yet.</div>}
          </div>
        </section>

        <section className="panel detail-panel">
          {detail ? <>
            <div className="detail-title"><div><p className="eyebrow">INCIDENT DETAIL</p><h2>{detail.incident.title}</h2></div><span className={`severity severity-${detail.incident.severity}`}>{detail.incident.severity}</span></div>
            <p>{detail.incident.description}</p>
            <dl className="facts"><div><dt>Status</dt><dd>{detail.incident.status.replaceAll("_", " ")}</dd></div><div><dt>Service</dt><dd>{serviceNames.get(detail.incident.service_id ?? "") ?? "Unassigned"}</dd></div><div><dt>Created</dt><dd>{formatTime(detail.incident.created_at)}</dd></div><div><dt>Investigation</dt><dd>{detail.investigation?.current_node.replaceAll("_", " ") ?? "Not started"}</dd></div><div><dt>Graph iterations</dt><dd>{detail.investigation?.iteration_count ?? 0}</dd></div><div><dt>Tool calls</dt><dd>{detail.investigation?.tool_calls_count ?? 0}</dd></div></dl>
            {canWrite && <div className="actions"><button disabled={working || Boolean(detail.investigation) || ["cancelled", "resolved"].includes(detail.incident.status)} onClick={investigate}>{detail.investigation ? "Investigation started" : "Start investigation"}</button><button className="danger" disabled={working || detail.incident.status === "cancelled"} onClick={cancel}>Cancel incident</button></div>}
            {detail.diagnosis && <section className="diagnosis-card">
              <div><p className="eyebrow">ROOT-CAUSE REPORT</p><span>{Math.round(Number(detail.diagnosis.confidence) * 100)}% confidence estimate</span></div>
              <h3>{detail.diagnosis.root_cause}</h3>
              <p>{detail.diagnosis.summary}</p>
              <div className="citations">{detail.diagnosis.evidence_ids.map((id, index) => <a href={`#evidence-${id}`} key={id}>Evidence {index + 1}</a>)}</div>
              {detail.diagnosis.limitations.length > 0 && <details><summary>Limitations</summary><ul>{detail.diagnosis.limitations.map(item => <li key={item}>{item}</li>)}</ul></details>}
            </section>}
            <div className="hypothesis-heading"><div><p className="eyebrow">HYPOTHESES</p><span>{hypotheses.length} candidates</span></div>{detail.investigation?.status === "running" && <span className="live"><i /> graph running</span>}</div>
            <div className="hypothesis-list">
              {hypotheses.map(hypothesis => <article className="hypothesis-card" key={hypothesis.id}>
                <div><span className={`status status-${hypothesis.status}`}>{hypothesis.status}</span><strong>{Math.round(Number(hypothesis.confidence) * 100)}%</strong></div>
                <h3>{hypothesis.title}</h3><p>{hypothesis.description}</p>
                <details><summary>Validation plan</summary><ol>{hypothesis.validation_plan.map(item => <li key={item}>{item}</li>)}</ol></details>
              </article>)}
              {!hypotheses.length && <p className="empty">No hypotheses yet.</p>}
            </div>
            <div className="evidence-heading"><div><p className="eyebrow">EVIDENCE</p><span>{evidence.length} records</span></div></div>
            <div className="evidence-list">
              {evidence.map(item => <article className="evidence-card" id={`evidence-${item.id}`} key={item.id}>
                <div><span className={`evidence-type evidence-${item.type}`}>{item.type}</span><time>{formatTime(item.observed_at ?? item.created_at)}</time></div>
                <strong>{item.summary}</strong>
                <p>{item.source} · {item.tool_name}</p>
                {(evidenceUsage.get(item.id) ?? []).map(title => <small className="used-by" key={title}>Supports: {title}</small>)}
                <details><summary>View raw</summary><pre>{item.content}</pre><small>SHA-256 {item.content_hash}</small></details>
              </article>)}
              {!evidence.length && <p className="empty">No evidence collected for this incident.</p>}
            </div>
            <div className="timeline-heading"><p className="eyebrow">TIMELINE</p><span className="live"><i /> live</span></div>
            <ol className="timeline">
              {detail.timeline.map(event => <li key={event.id}><span className="timeline-marker" /><div><strong>{event.event_type.replaceAll(".", " ")}</strong><p>{event.actor_type} · {event.actor_id}</p><time>{formatTime(event.created_at)}</time></div></li>)}
            </ol>
          </> : <div className="empty detail-empty"><span>↖</span><strong>Select an incident</strong><p>Its status, investigation, and append-only event timeline will appear here.</p></div>}
        </section>
      </div>
      <footer>Phase 3 runs a bounded evidence graph and produces cited diagnoses. Remediation begins in Phase 5.</footer>
    </main>
  );
}
