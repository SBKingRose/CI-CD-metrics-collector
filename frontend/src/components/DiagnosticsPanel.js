import React from 'react';
import './DiagnosticsPanel.css';

function DiagnosticsPanel({ diagnostics }) {

  return (
    <div className="card">
      <h2>Actionable Diagnostics</h2>
      {diagnostics.length === 0 ? (
        <p className="no-diagnostics">No diagnostics available. Trigger data collection to generate insights.</p>
      ) : (
        <div className="diagnostics-list">
          {diagnostics.slice(0, 10).map(diag => (
            <details key={diag.id} className={`diagnostic-item severity-${diag.severity}`}>
              <summary className="diagnostic-title">{diag.title}</summary>
              <div className="diagnostic-message">{diag.message}</div>
              {diag.diagnostic_metadata && (
                <pre className="diag-meta">{JSON.stringify(diag.diagnostic_metadata, null, 2)}</pre>
              )}
            </details>
          ))}
        </div>
      )}
    </div>
  );
}

export default DiagnosticsPanel;

