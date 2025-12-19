import React, { useState } from 'react';
import './GlobalMetrics.css';

const neonColors = [
  '#00fff7', '#ff00ea', '#fffb00', '#00ff6a', '#ff6a00', '#6a00ff', '#00aaff', '#ff0077', '#77ff00', '#ff0077'
];

function GlobalMetrics({ summary, loading, repositories }) {
  const [showBuildBreakdown, setShowBuildBreakdown] = useState(false);

  if (loading) {
    return (
      <div className="card glass-card p-3 neon-bg">
        <h2 style={{color: '#fff'}}>Org-wide Metrics</h2>
        <div className="loading" style={{color: '#fff'}}>Loading summary...</div>
      </div>
    );
  }

  if (!summary) {
    return null;
  }

  // Use build_stats.json format for all values
  const buildStats = summary.build_stats || {};
  const repoList = Object.keys(buildStats);
  const totalBuildMinutes = repoList.reduce((acc, repo) => {
    const val = buildStats[repo]?.build_minutes_used || '0d 0h 0m 0s';
    // Parse minutes from string
    const parts = val.split(' ');
    let mins = 0;
    for (let part of parts) {
      if (part.endsWith('d')) mins += parseInt(part) * 24 * 60;
      if (part.endsWith('h')) mins += parseInt(part) * 60;
      if (part.endsWith('m')) mins += parseInt(part);
    }
    return acc + mins;
  }, 0);

  const openBuildBreakdown = () => setShowBuildBreakdown(true);
  const closeBuildBreakdown = () => setShowBuildBreakdown(false);

  return (
    <div className="card glass-card p-3 neon-bg">
      <div className="d-flex justify-content-between align-items-start mb-2">
        <div>
          <p className="text-muted small mb-0" style={{color: '#fff'}}>Org-wide metrics</p>
          <h3 className="mb-0" style={{color: '#fff'}}>Delivery Health Overview</h3>
        </div>
        <div className="badge bg-primary" style={{background: 'linear-gradient(90deg,#00fff7,#ff00ea)', color: '#222'}}>{repoList.length} repos</div>
      </div>

      <div className="row g-2">
        <div className="col-md-3">
          <div className="card metric-card h-100 text-center p-3 neon-card" role="button" onClick={openBuildBreakdown}>
            <div className="metric-label" style={{color: '#fff'}}>Build Minutes</div>
            <div className="metric-value display-6" style={{color: '#fff'}}>{totalBuildMinutes}</div>
            <div className="metric-sublabel" style={{color: '#fff'}}>Total (from file)</div>
            <div className="text-muted small mt-2" style={{color: '#fff'}}>Click to view per-repo breakdown</div>
          </div>
        </div>

        {/* Mock PR velocity, deployment frequency, slow pipelines for demo */}
        <div className="col-md-3">
          <div className="card metric-card h-100 p-3 neon-card">
            <div className="metric-label" style={{color: '#fff'}}>PR Velocity (median)</div>
            <div className="metric-value h2" style={{color: '#fff'}}>2.1h</div>
            <div className="metric-sublabel" style={{color: '#fff'}}>P90: 4.3h</div>
          </div>
        </div>

        <div className="col-md-3">
          <div className="card metric-card h-100 p-3 neon-card">
            <div className="metric-label" style={{color: '#fff'}}>Deployment Frequency</div>
            <div className="metric-value h2" style={{color: '#fff'}}>12</div>
            <div className="metric-sublabel" style={{color: '#fff'}}>Last 30 days (all repos)</div>
          </div>
        </div>

        <div className="col-md-3">
          <div className="card metric-card h-100 p-3 neon-card">
            <div className="metric-label" style={{color: '#fff'}}>Slow Pipelines</div>
            <div className="metric-value h2" style={{color: '#fff'}}>3</div>
            <div className="metric-sublabel" style={{color: '#fff'}}>Above P90 threshold</div>
          </div>
        </div>
      </div>

      {/* Build minutes modal / panel */}
      {showBuildBreakdown && (
        <div className="build-breakdown-modal neon-modal">
          <div className="build-breakdown-content card p-3 neon-card">
            <div className="d-flex justify-content-between align-items-center">
              <h5 style={{color: '#fff'}}>Build Minutes: per-repository</h5>
              <button className="btn btn-sm btn-outline-light" style={{color: '#fff', borderColor: '#fff'}} onClick={closeBuildBreakdown}>Close</button>
            </div>
            <div className="repo-bars mt-3">
              {repoList.length > 0 ? (
                repoList.map((repo, idx) => {
                  const stats = buildStats[repo];
                  // Parse minutes for bar width
                  const val = stats.build_minutes_used || '0d 0h 0m 0s';
                  const parts = val.split(' ');
                  let mins = 0;
                  for (let part of parts) {
                    if (part.endsWith('d')) mins += parseInt(part) * 24 * 60;
                    if (part.endsWith('h')) mins += parseInt(part) * 60;
                    if (part.endsWith('m')) mins += parseInt(part);
                  }
                  const pct = totalBuildMinutes ? (mins / totalBuildMinutes) : 0;
                  const widthPct = Math.max(8, Math.round(pct * 100));
                  const color = neonColors[idx % neonColors.length];
                  return (
                    <div key={repo} className="repo-bar d-flex align-items-center mb-2">
                      <div className="repo-name me-2" style={{width: '180px', color: '#fff', fontWeight: 600}}>{repo}</div>
                      <div className="bar bg-dark flex-grow-1 position-relative" style={{height: '28px', borderRadius: '16px', background: 'rgba(30,41,59,0.85)'}}>
                        <div className="bar-fill" style={{width: `${widthPct}%`, background: `linear-gradient(90deg,${color},#222)`}}></div>
                        <div className="bar-text position-absolute end-0 pe-2 small" style={{color: '#fff', fontWeight: 600}}>{stats.build_minutes_used}</div>
                        <div className="bar-text position-absolute start-0 ps-2 small" style={{color: '#fff', fontWeight: 600}}>{stats.builds} builds</div>
                      </div>
                      <div className="ms-2" style={{color: '#fff', fontSize: '0.9rem'}}>{stats.build_duration}</div>
                    </div>
                  );
                })
              ) : (
                <div className="text-muted" style={{color: '#fff'}}>No repositories available</div>
              )}
            </div>
            <div className="text-muted small mt-3" style={{color: '#fff'}}>Source: build_stats.json</div>
          </div>
        </div>
      )}
    </div>
  );
}

export default GlobalMetrics;

