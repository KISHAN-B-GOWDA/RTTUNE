import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const API = "http://127.0.0.1:8000";

type Experiment = {
  id: number;
  name: string;
  description: string | null;
  mode: string;
  packet_count: number;
  base_delay: number;
  jitter: number;
  packet_loss: number;
  status: string;
  started_at: string | null;
  completed_at: string | null;
};

type Measurement = {
  id: number;
  experiment_id: number;
  sequence_number: number;
  rtt: number;
  srtt: number;
  rttvar: number;
  rto: number;
  was_retransmission: boolean;
  timeout_occurred: boolean;
  timestamp: string;
};

type Summary = {
  total_measurements: number;
  successful_measurements: number;
  timeouts: number;
  average_rtt: number | null;
  minimum_rtt: number | null;
  maximum_rtt: number | null;
  average_rto: number | null;
  latest_rto: number | null;
  latest_srtt: number | null;
  latest_rttvar: number | null;
};

type Comparison = {
  fixed: {
    rto: number;
    timeouts: number;
    average_rto: number;
    results: { sequence: number; rtt: number | null; rto: number; timeout: boolean }[];
  };
  adaptive: {
    timeouts: number;
    average_rto: number;
    results: { sequence: number; rtt: number | null; rto: number; timeout: boolean }[];
  };
};

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail ?? message;
    } catch {
      // Keep fallback message.
    }
    throw new Error(message);
  }

  return response.json();
}

function seconds(value: number | null | undefined): string {
  return value == null ? "—" : `${(value * 1000).toFixed(2)} ms`;
}

function statusClass(status: string): string {
  return `status status-${status}`;
}

export default function App() {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [experimentId, setExperimentId] = useState<number | null>(() => {
    const saved = localStorage.getItem("rttune_experiment_id");
    return saved ? Number(saved) : null;
  });

  const [experiment, setExperiment] = useState<Experiment | null>(null);
  const [measurements, setMeasurements] = useState<Measurement[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [comparison, setComparison] = useState<Comparison | null>(null);

  const [name, setName] = useState("RTTune Experiment");
  const [description, setDescription] = useState("Adaptive RTO analysis");
  const [mode, setMode] = useState("adaptive");
  const [packetCount, setPacketCount] = useState(50);
  const [baseDelay, setBaseDelay] = useState(0.05);
  const [jitter, setJitter] = useState(0.01);
  const [packetLoss, setPacketLoss] = useState(0);

  const [manualRtt, setManualRtt] = useState(0.05);
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function loadExperiments() {
    const data = await api<Experiment[]>("/api/experiments");
    setExperiments(data);
    if (experimentId && data.some((item) => item.id === experimentId)) {
      return;
    }
    if (data.length > 0) {
      setExperimentId(data[0].id);
      localStorage.setItem("rttune_experiment_id", String(data[0].id));
    }
  }

  async function loadExperimentData(id: number) {
    const [exp, rows, stats] = await Promise.all([
      api<Experiment>(`/api/experiments/${id}`),
      api<Measurement[]>(`/api/experiments/${id}/measurements`),
      api<Summary>(`/api/experiments/${id}/summary`),
    ]);
    setExperiment(exp);
    setMeasurements(rows);
    setSummary(stats);
  }

  useEffect(() => {
    void loadExperiments().catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (experimentId == null) return;
    void loadExperimentData(experimentId).catch((e) => setError(e.message));
  }, [experimentId]);

  async function createExperiment() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const created = await api<Experiment>("/api/experiments", {
        method: "POST",
        body: JSON.stringify({
          name,
          description,
          mode,
          packet_count: packetCount,
          base_delay: baseDelay,
          jitter,
          packet_loss: packetLoss,
        }),
      });
      setExperimentId(created.id);
      localStorage.setItem("rttune_experiment_id", String(created.id));
      await loadExperiments();
      await loadExperimentData(created.id);
      setMessage(`Experiment #${created.id} created.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create experiment.");
    } finally {
      setBusy(false);
    }
  }

  async function selectExperiment(id: number) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api(`/api/experiments/${id}/select`, { method: "POST" });
      setExperimentId(id);
      localStorage.setItem("rttune_experiment_id", String(id));
      setComparison(null);
      await loadExperimentData(id);
      setMessage(`Experiment #${id} selected.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to select experiment.");
    } finally {
      setBusy(false);
    }
  }

  async function simulate() {
    if (!experimentId) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<{ successful_packets: number; lost_packets: number }>(
        `/api/experiments/${experimentId}/simulate`,
        { method: "POST" },
      );
      await loadExperimentData(experimentId);
      await loadExperiments();
      setMessage(
        `Simulation complete: ${result.successful_packets} successful, ${result.lost_packets} lost.`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Simulation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function recordRtt() {
    if (!experimentId) return;
    setBusy(true);
    setError("");
    try {
      await api("/api/rto/update", {
        method: "POST",
        body: JSON.stringify({ rtt: manualRtt }),
      });
      await loadExperimentData(experimentId);
      await loadExperiments();
      setMessage(`Recorded RTT ${(manualRtt * 1000).toFixed(2)} ms.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "RTT update failed.");
    } finally {
      setBusy(false);
    }
  }

  async function recordTimeout() {
    if (!experimentId) return;
    setBusy(true);
    setError("");
    try {
      await api(`/api/experiments/${experimentId}/timeout`, { method: "POST" });
      await loadExperimentData(experimentId);
      await loadExperiments();
      setMessage("Timeout recorded and RTO backed off.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Timeout failed.");
    } finally {
      setBusy(false);
    }
  }

  async function compare() {
    if (!experimentId) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<Comparison>(
        `/api/experiments/${experimentId}/compare`,
        { method: "POST" },
      );
      setComparison(result);
      setMessage("Fixed vs adaptive comparison generated.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Comparison failed.");
    } finally {
      setBusy(false);
    }
  }

  async function deleteExperiment() {
    if (!experimentId) return;
    if (!window.confirm(`Delete experiment #${experimentId}?`)) return;

    setBusy(true);
    try {
      await api(`/api/experiments/${experimentId}`, { method: "DELETE" });
      localStorage.removeItem("rttune_experiment_id");
      setExperimentId(null);
      setExperiment(null);
      setMeasurements([]);
      setSummary(null);
      setComparison(null);
      await loadExperiments();
      setMessage("Experiment deleted.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed.");
    } finally {
      setBusy(false);
    }
  }

  const chartData = useMemo(
    () =>
      measurements.map((m) => ({
        sequence: m.sequence_number,
        rtt: m.timeout_occurred ? null : m.rtt * 1000,
        rto: m.rto * 1000,
        srtt: m.srtt * 1000,
      })),
    [measurements],
  );

  const comparisonData = useMemo(() => {
    if (!comparison) return [];
    return comparison.fixed.results.map((fixed, index) => ({
      sequence: fixed.sequence,
      rtt: fixed.rtt == null ? null : fixed.rtt * 1000,
      fixedRto: fixed.rto * 1000,
      adaptiveRto: comparison.adaptive.results[index].rto * 1000,
    }));
  }, [comparison]);

  const filteredExperiments = experiments.filter((item) =>
    `${item.name} ${item.id} ${item.status}`.toLowerCase().includes(search.toLowerCase()),
  );

  function exportCsv() {
    if (!experimentId) return;
    window.open(`${API}/api/experiments/${experimentId}/export.csv`, "_blank");
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <div className="brand">RTTune</div>
          <div className="subtitle">Adaptive Retransmission Timeout Monitoring System</div>
        </div>
        <div className="header-badge">Computer Networks</div>
      </header>

      <main className="page">
        <section className="hero">
          <div>
            <h1>Understand where retransmission timing adapts.</h1>
            <p>
              Simulate RTT behavior, observe SRTT / RTTVAR / RTO changes, trigger
              timeout backoff, and compare fixed and adaptive timeout strategies.
            </p>
          </div>
          <div className="hero-equation">
            <span>RTO = SRTT + max(G, K × RTTVAR)</span>
            <small>α = 1/8 · β = 1/4 · K = 4</small>
          </div>
        </section>

        <section className="panel">
          <div className="panel-title">
            <div>
              <h2>Create experiment</h2>
              <p>Configure the simulated network conditions.</p>
            </div>
          </div>

          <div className="form-grid">
            <label>
              Experiment name
              <input value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            <label>
              Description
              <input value={description} onChange={(e) => setDescription(e.target.value)} />
            </label>
            <label>
              Mode
              <select value={mode} onChange={(e) => setMode(e.target.value)}>
                <option value="adaptive">Adaptive</option>
                <option value="fixed">Fixed</option>
                <option value="comparison">Comparison</option>
              </select>
            </label>
            <label>
              Packets
              <input
                type="number"
                min="1"
                max="10000"
                value={packetCount}
                onChange={(e) => setPacketCount(Number(e.target.value))}
              />
            </label>
            <label>
              Base delay (s)
              <input
                type="number"
                step="0.001"
                min="0.001"
                value={baseDelay}
                onChange={(e) => setBaseDelay(Number(e.target.value))}
              />
            </label>
            <label>
              Jitter (s)
              <input
                type="number"
                step="0.001"
                min="0"
                value={jitter}
                onChange={(e) => setJitter(Number(e.target.value))}
              />
            </label>
            <label>
              Packet loss (%)
              <input
                type="number"
                step="1"
                min="0"
                max="100"
                value={packetLoss}
                onChange={(e) => setPacketLoss(Number(e.target.value))}
              />
            </label>
          </div>

          <div className="button-row">
            <button className="primary-button" disabled={busy} onClick={() => void createExperiment()}>
              Create experiment
            </button>
          </div>

          {message && <div className="message">{message}</div>}
          {error && <div className="error">{error}</div>}
        </section>

        <div className="layout">
          <aside className="panel history">
            <div className="panel-title">
              <div>
                <h2>Experiment history</h2>
                <p>{experiments.length} saved experiments</p>
              </div>
            </div>

            <input
              className="search"
              placeholder="Search experiments..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />

            <div className="history-list">
              {filteredExperiments.map((item) => (
                <button
                  key={item.id}
                  className={`history-item ${item.id === experimentId ? "selected" : ""}`}
                  onClick={() => void selectExperiment(item.id)}
                >
                  <div>
                    <strong>#{item.id} · {item.name}</strong>
                    <span>{item.packet_count} packets · {(item.base_delay * 1000).toFixed(0)} ms base</span>
                  </div>
                  <span className={statusClass(item.status)}>{item.status}</span>
                </button>
              ))}
              {filteredExperiments.length === 0 && (
                <div className="empty-small">No experiments found.</div>
              )}
            </div>
          </aside>

          <section className="content">
            <section className="panel">
              <div className="panel-title">
                <div>
                  <h2>{experiment ? `Experiment #${experiment.id}` : "No experiment selected"}</h2>
                  <p>{experiment?.description || "Create or select an experiment to begin."}</p>
                </div>
                {experiment && <span className={statusClass(experiment.status)}>{experiment.status}</span>}
              </div>

              {experiment && (
                <>
                  <div className="cards">
                    <div className="stat-card">
                      <span>Average RTT</span>
                      <strong>{seconds(summary?.average_rtt)}</strong>
                    </div>
                    <div className="stat-card">
                      <span>Latest SRTT</span>
                      <strong>{seconds(summary?.latest_srtt)}</strong>
                    </div>
                    <div className="stat-card">
                      <span>Latest RTO</span>
                      <strong>{seconds(summary?.latest_rto)}</strong>
                    </div>
                    <div className="stat-card">
                      <span>RTTVAR</span>
                      <strong>{seconds(summary?.latest_rttvar)}</strong>
                    </div>
                    <div className="stat-card">
                      <span>Timeouts</span>
                      <strong>{summary?.timeouts ?? 0}</strong>
                    </div>
                    <div className="stat-card">
                      <span>Samples</span>
                      <strong>{summary?.successful_measurements ?? 0}</strong>
                    </div>
                  </div>

                  <div className="control-strip">
                    <div>
                      <label>Manual RTT (seconds)</label>
                      <input
                        type="number"
                        min="0.001"
                        step="0.001"
                        value={manualRtt}
                        onChange={(e) => setManualRtt(Number(e.target.value))}
                      />
                    </div>
                    <button disabled={busy} className="primary-button" onClick={() => void recordRtt()}>
                      Record RTT
                    </button>
                    <button disabled={busy} className="secondary-button" onClick={() => void simulate()}>
                      Run simulation
                    </button>
                    <button disabled={busy} className="secondary-button" onClick={() => void recordTimeout()}>
                      Trigger timeout
                    </button>
                    <button disabled={busy} className="secondary-button" onClick={() => void compare()}>
                      Compare RTO
                    </button>
                    <button disabled={busy} className="secondary-button" onClick={exportCsv}>
                      Export CSV
                    </button>
                    <button disabled={busy} className="danger-button" onClick={() => void deleteExperiment()}>
                      Delete
                    </button>
                  </div>
                </>
              )}
            </section>

            {experiment && (
              <>
                <section className="panel">
                  <div className="panel-title">
                    <div>
                      <h2>RTT and RTO timeline</h2>
                      <p>Successful RTT samples are shown alongside the adaptive RTO.</p>
                    </div>
                  </div>
                  <div className="chart">
                    {chartData.length ? (
                      <ResponsiveContainer width="100%" height={360}>
                        <LineChart data={chartData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="sequence" />
                          <YAxis unit=" ms" />
                          <Tooltip formatter={(value) => `${Number(value).toFixed(2)} ms`} />
                          <Legend />
                          <Line type="monotone" dataKey="rtt" name="RTT" connectNulls={false} dot={false} />
                          <Line type="monotone" dataKey="srtt" name="SRTT" dot={false} />
                          <Line type="monotone" dataKey="rto" name="RTO" dot={false} />
                        </LineChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="empty-chart">No measurements yet. Record an RTT or run a simulation.</div>
                    )}
                  </div>
                </section>

                {comparison && (
                  <section className="panel">
                    <div className="panel-title">
                      <div>
                        <h2>Fixed vs adaptive RTO</h2>
                        <p>Both strategies use the same generated RTT/loss sequence.</p>
                      </div>
                    </div>

                    <div className="cards comparison-cards">
                      <div className="stat-card">
                        <span>Fixed timeouts</span>
                        <strong>{comparison.fixed.timeouts}</strong>
                      </div>
                      <div className="stat-card">
                        <span>Adaptive timeouts</span>
                        <strong>{comparison.adaptive.timeouts}</strong>
                      </div>
                      <div className="stat-card">
                        <span>Fixed average RTO</span>
                        <strong>{seconds(comparison.fixed.average_rto)}</strong>
                      </div>
                      <div className="stat-card">
                        <span>Adaptive average RTO</span>
                        <strong>{seconds(comparison.adaptive.average_rto)}</strong>
                      </div>
                    </div>

                    <div className="chart">
                      <ResponsiveContainer width="100%" height={340}>
                        <LineChart data={comparisonData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="sequence" />
                          <YAxis unit=" ms" />
                          <Tooltip formatter={(value) => `${Number(value).toFixed(2)} ms`} />
                          <Legend />
                          <Line type="monotone" dataKey="fixedRto" name="Fixed RTO" dot={false} />
                          <Line type="monotone" dataKey="adaptiveRto" name="Adaptive RTO" dot={false} />
                          <Line type="monotone" dataKey="rtt" name="RTT" dot={false} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </section>
                )}

                <section className="panel">
                  <div className="panel-title">
                    <div>
                      <h2>Measurement history</h2>
                      <p>Latest measurements are listed first.</p>
                    </div>
                  </div>

                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Seq</th>
                          <th>RTT</th>
                          <th>SRTT</th>
                          <th>RTTVAR</th>
                          <th>RTO</th>
                          <th>Event</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...measurements].reverse().slice(0, 100).map((m) => (
                          <tr key={m.id}>
                            <td>{m.sequence_number}</td>
                            <td>{m.timeout_occurred ? "TIMEOUT" : seconds(m.rtt)}</td>
                            <td>{seconds(m.srtt)}</td>
                            <td>{seconds(m.rttvar)}</td>
                            <td>{seconds(m.rto)}</td>
                            <td>
                              {m.timeout_occurred ? (
                                <span className="event timeout">Timeout / backoff</span>
                              ) : (
                                <span className="event success">RTT sample</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {measurements.length === 0 && <div className="empty-small">No measurements yet.</div>}
                  </div>
                </section>
              </>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
