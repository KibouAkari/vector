'use client';

import {
  useEffect,
  useState
} from 'react';

import {
  Activity,
  ArrowUpRight,
  RefreshCw
} from 'lucide-react';

import {
  modelIntelligenceRows
} from '../../lib/model-intelligence-summary.mjs';

const number = value =>
  Number(value).toLocaleString('en-CH');

const shown = value =>
  value == null ? '—' : number(value);

export default function ModelIntelligence({
  providers
}) {
  const [days, setDays] = useState(7);
  const [revision, setRevision] = useState(0);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const controller = new AbortController();

    setLoading(true);
    setError(null);

    fetch(`/api/models/intelligence?days=${days}`, {
      cache: 'no-store',
      signal: controller.signal
    })
      .then(async response => {
        if (!response.ok) {
          throw new Error('Could not load metrics.');
        }

        return response.json();
      })
      .then(data => {
        if (!controller.signal.aborted) {
          setReport(data);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setError(
            'Metrics temporarily unavailable.'
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();

  }, [days, revision]);

  const rows = modelIntelligenceRows(
    providers,
    report?.metrics || []
  );

  const attempts = rows.reduce(
    (sum, row) => sum + row.attempts,
    0
  );

  const successes = rows.reduce(
    (sum, row) => sum + row.successes,
    0
  );

  const successRate = attempts
    ? `${(100 * successes / attempts).toFixed(1)}%`
    : '—';

  const ready =
    !loading &&
    !error &&
    report?.status === 'ready';

  return (
    <section
      className="vmi"
      aria-label="Model Intelligence"
    >
      <header className="vmi-header">
        <div>
          <div className="vmi-eyebrow">
            <Activity size={13} />
            OBSERVABILITY / VECTOR AUTO
          </div>

          <h2>
            Model Intelligence
            <ArrowUpRight
              size={18}
              aria-hidden="true"
            />
          </h2>

          <p>
            Measured provider performance.
            Read-only; routing is unchanged.
          </p>
        </div>

        <div className="vmi-controls">
          <div
            className="vmi-period"
            role="group"
            aria-label="Reporting window"
          >
            {[7, 30].map(value => (
              <button
                key={value}
                type="button"
                aria-pressed={days === value}
                onClick={() => setDays(value)}
              >
                {value}d
              </button>
            ))}
          </div>

          <button
            type="button"
            className="vmi-refresh"
            aria-label="Refresh metrics"
            onClick={() =>
              setRevision(value => value + 1)
            }
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </header>

      <div className="vmi-stats">
        <div>
          <span>Provider connections</span>
          <strong>{rows.length}</strong>
        </div>

        <div>
          <span>Recorded requests</span>
          <strong>
            {ready ? number(attempts) : '—'}
          </strong>
        </div>

        <div>
          <span>Observed success rate</span>
          <strong>
            {ready ? successRate : '—'}
          </strong>
        </div>
      </div>

      {error && (
        <p className="vmi-notice" role="alert">
          {error}
        </p>
      )}

      {!error && loading && (
        <p className="vmi-notice" role="status">
          Loading observations…
        </p>
      )}

      {!loading &&
        !error &&
        report?.status === 'not-configured' && (
          <p className="vmi-notice">
            Detailed model analytics are not active yet.
            Your connections and automatic routing remain available.
          </p>
        )}

      {!loading &&
        !error &&
        report?.status === 'ready' &&
        attempts === 0 && (
          <p className="vmi-notice">
            No recorded requests in this period.
            Telemetry is opt-in; unrecorded calls
            cannot be measured.
          </p>
        )}

      {ready && attempts > 0 && (
      <div className="vmi-scroll">
        <table className="vmi-table">
          <thead>
            <tr>
              <th>Connection</th>
              <th>Requests</th>
              <th>Success</th>
              <th>Average</th>
              <th>P95</th>
              <th>Tokens in / out</th>
            </tr>
          </thead>

          <tbody>
            {rows.map(row => (
              <tr key={row.id}>
                <td>
                  <strong>{row.label}</strong>
                  <small>
                    {row.provider}
                    {' · '}
                    {row.enabled
                      ? 'Enabled'
                      : 'Disabled'}
                  </small>
                </td>

                <td>
                  {ready ? shown(row.attempts) : '—'}
                </td>

                <td>
                  {ready && row.successRate != null
                    ? `${row.successRate}%`
                    : '—'}
                </td>

                <td>
                  {ready && row.averageMs != null
                    ? `${shown(row.averageMs)} ms`
                    : '—'}
                </td>

                <td>
                  {ready && row.p95Ms != null
                    ? `${shown(row.p95Ms)} ms`
                    : '—'}
                </td>

                <td>
                  {ready
                    ? `${shown(row.inputTokens)} / ${shown(row.outputTokens)}`
                    : '—'}

                  {row.attempts > 0 && ready && (
                    <small>
{row.inputSamples}
                      {' input / '}
                      {row.outputSamples}
                      {' output samples across '}
                      {row.attempts}
                      {' requests'}
                    </small>
                  )}
                </td>
              </tr>
            ))}

            {rows.length === 0 && (
              <tr>
                <td colSpan={6}>
                  No owned connections to display.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      )}

      {ready && attempts > 0 && <footer className="vmi-footnote">
        Includes recorded requests made using your
        provider connections, including shared usage.
        Missing and dropped samples are not estimated.
        CHF spending cannot yet be attributed reliably
        to individual connections.
      </footer>}
    </section>
  );
}
