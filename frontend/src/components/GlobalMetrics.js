import React, { useState } from 'react';
import './GlobalMetrics.css';

const neonColors = [
  '#00fff7', '#ff00ea', '#fffb00', '#00ff6a', '#ff6a00', '#6a00ff', '#00aaff', '#ff0077', '#77ff00', '#ff0077'
];

function GlobalMetrics({ summary, loading, repositories }) {
  const [showBuildBreakdown, setShowBuildBreakdown] = useState(false);
  const [showPRBreakdown, setShowPRBreakdown] = useState(false);
  const [showDeploymentBreakdown, setShowDeploymentBreakdown] = useState(false);
  const [showSlowPipelinesBreakdown, setShowSlowPipelinesBreakdown] = useState(false);
  const [prByRepo, setPRByRepo] = useState(null);
  const [deploymentByRepo, setDeploymentByRepo] = useState(null);
  const [slowPipelinesByRepo, setSlowPipelinesByRepo] = useState(null);

  const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  const loadPRByRepo = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/metrics/pr-velocity-by-repo`);
      const data = await response.json();
      setPRByRepo(data);
    } catch (error) {
      console.error('Error loading PR velocity by repo:', error);
    }
  };

  const loadDeploymentByRepo = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/metrics/deployment-frequency-by-repo`);
      const data = await response.json();
      setDeploymentByRepo(data);
    } catch (error) {
      console.error('Error loading deployment frequency by repo:', error);
    }
  };

  const loadSlowPipelinesByRepo = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/metrics/slow-pipelines-by-repo`);
      const data = await response.json();
      setSlowPipelinesByRepo(data);
    } catch (error) {
      console.error('Error loading slow pipelines by repo:', error);
    }
  };

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

  // Use build_minutes_28_file for build minutes (28th to 28th period)
  const buildMinutes28 = summary.build_minutes_28_file || {};
  const buildMinutesByRepo = buildMinutes28.by_repo || {};
  const totalBuildMinutes = buildMinutes28.total_minutes || 0;
  
  // Also get build stats for builds count
  const buildStats = summary.build_stats || {};
  const repoList = Object.keys(buildMinutesByRepo).length > 0 ? Object.keys(buildMinutesByRepo) : Object.keys(buildStats);

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
            <div className="metric-value display-6" style={{color: '#fff'}}>{totalBuildMinutes.toFixed(2)}</div>
            <div className="metric-sublabel" style={{color: '#fff'}}>Total (from file)</div>
            <div className="text-muted small mt-2" style={{color: '#fff'}}>Click to view per-repo breakdown</div>
          </div>
        </div>

        {/* PR velocity, deployment frequency, slow pipelines from API */}
        <div className="col-md-3">
          <div className="card metric-card h-100 p-3 neon-card" role="button" onClick={() => {
            setShowPRBreakdown(true);
            if (!prByRepo) loadPRByRepo();
          }}>
            <div className="metric-label" style={{color: '#fff'}}>PR Velocity (median)</div>
            <div className="metric-value h2" style={{color: '#fff'}}>
              {summary?.pr_velocity?.median_hours 
                ? `${summary.pr_velocity.median_hours.toFixed(1)}h`
                : 'N/A'}
            </div>
            <div className="metric-sublabel" style={{color: '#fff'}}>P90: {summary?.pr_velocity?.p90_hours?.toFixed(1)}h</div>
            <div className="text-muted small mt-2" style={{color: '#fff'}}>Click to view per-repo breakdown</div>
          </div>
        </div>

        <div className="col-md-3">
          <div className="card metric-card h-100 p-3 neon-card" role="button" onClick={() => {
            setShowDeploymentBreakdown(true);
            if (!deploymentByRepo) loadDeploymentByRepo();
          }}>
            <div className="metric-label" style={{color: '#fff'}}>Deployment Frequency</div>
            <div className="metric-value h2" style={{color: '#fff'}}>
              {summary?.deployment_frequency?.total || summary?.deployment_frequency?.count || 0}
            </div>
            <div className="metric-sublabel" style={{color: '#fff'}}>Last 30 days</div>
            <div className="text-muted small mt-2" style={{color: '#fff'}}>Click to view per-repo breakdown</div>
          </div>
        </div>

        <div className="col-md-3">
          <div className="card metric-card h-100 p-3 neon-card" role="button" onClick={() => {
            setShowSlowPipelinesBreakdown(true);
            if (!slowPipelinesByRepo) loadSlowPipelinesByRepo();
          }}>
            <div className="metric-label" style={{color: '#fff'}}>Slow Pipelines</div>
            <div className="metric-value h2" style={{color: '#fff'}}>
              {summary?.slow_pipelines?.total || 0}
            </div>
            <div className="metric-sublabel" style={{color: '#fff'}}>Above P90 threshold</div>
            <div className="text-muted small mt-2" style={{color: '#fff'}}>Click to view per-repo breakdown</div>
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
                  const mins = buildMinutesByRepo[repo] || 0;
                  const stats = buildStats[repo] || {};
                  const pct = totalBuildMinutes ? (mins / totalBuildMinutes) : 0;
                  const widthPct = Math.max(8, Math.round(pct * 100));
                  const color = neonColors[idx % neonColors.length];
                  return (
                    <div key={repo} className="repo-bar d-flex align-items-center mb-2">
                      <div className="repo-name me-2" style={{width: '180px', color: '#fff', fontWeight: 600}}>{repo}</div>
                      <div className="bar bg-dark flex-grow-1 position-relative" style={{height: '28px', borderRadius: '16px', background: 'rgba(30,41,59,0.85)'}}>
                        <div className="bar-fill" style={{width: `${widthPct}%`, background: `linear-gradient(90deg,${color},#222)`}}></div>
                        <div className="bar-text position-absolute end-0 pe-2 small" style={{color: '#fff', fontWeight: 600}}>{mins.toFixed(2)} mins</div>
                        {stats.builds && (
                          <div className="bar-text position-absolute start-0 ps-2 small" style={{color: '#fff', fontWeight: 600}}>{stats.builds} builds</div>
                        )}
                      </div>
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

      {/* PR Velocity breakdown */}
      {showPRBreakdown && (
        <div className="build-breakdown-modal neon-modal">
          <div className="build-breakdown-content card p-3 neon-card">
            <div className="d-flex justify-content-between align-items-center">
              <h5 style={{color: '#fff'}}>PR Velocity: per-repository</h5>
              <button className="btn btn-sm btn-outline-light" style={{color: '#fff', borderColor: '#fff'}} onClick={() => setShowPRBreakdown(false)}>✕ Close</button>
            </div>
            <div className="table-responsive mt-3">
              <table className="table table-dark table-striped">
                <thead>
                  <tr>
                    <th>Repository</th>
                    <th>Median (hours)</th>
                    <th>P90 (hours)</th>
                    <th>Count</th>
                  </tr>
                </thead>
                <tbody>
                  {prByRepo ? (
                    Object.entries(prByRepo).map(([slug, data]) => (
                      <tr key={slug}>
                        <td><b>{data.name || slug}</b></td>
                        <td>{data.median_hours ? data.median_hours.toFixed(1) : 'N/A'}</td>
                        <td>{data.p90_hours ? data.p90_hours.toFixed(1) : 'N/A'}</td>
                        <td>{data.count || 0}</td>
                      </tr>
                    ))
                  ) : (
                    <tr><td colSpan="4" style={{color: '#fff'}}>Loading...</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Deployment Frequency breakdown */}
      {showDeploymentBreakdown && (
        <div className="build-breakdown-modal neon-modal">
          <div className="build-breakdown-content card p-3 neon-card">
            <div className="d-flex justify-content-between align-items-center">
              <h5 style={{color: '#fff'}}>Deployment Frequency: per-repository (Last 30 days)</h5>
              <button className="btn btn-sm btn-outline-light" style={{color: '#fff', borderColor: '#fff'}} onClick={() => setShowDeploymentBreakdown(false)}>✕ Close</button>
            </div>
            <div className="table-responsive mt-3">
              <table className="table table-dark table-striped">
                <thead>
                  <tr>
                    <th>Repository</th>
                    <th>Deployments</th>
                  </tr>
                </thead>
                <tbody>
                  {deploymentByRepo ? (
                    Object.entries(deploymentByRepo).map(([slug, data]) => (
                      <tr key={slug}>
                        <td><b>{data.name || slug}</b></td>
                        <td>{data.count || 0}</td>
                      </tr>
                    ))
                  ) : (
                    <tr><td colSpan="2" style={{color: '#fff'}}>Loading...</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Slow Pipelines breakdown */}
      {showSlowPipelinesBreakdown && (
        <div className="build-breakdown-modal neon-modal">
          <div className="build-breakdown-content card p-3 neon-card">
            <div className="d-flex justify-content-between align-items-center">
              <h5 style={{color: '#fff'}}>Slow Pipelines: per-repository</h5>
              <button className="btn btn-sm btn-outline-light" style={{color: '#fff', borderColor: '#fff'}} onClick={() => setShowSlowPipelinesBreakdown(false)}>✕ Close</button>
            </div>
            <div className="table-responsive mt-3">
              <table className="table table-dark table-striped">
                <thead>
                  <tr>
                    <th>Repository</th>
                    <th>Count</th>
                    <th>Worst Regression</th>
                    <th>Commit</th>
                  </tr>
                </thead>
                <tbody>
                  {slowPipelinesByRepo ? (
                    Object.entries(slowPipelinesByRepo).map(([slug, data]) => (
                      <tr key={slug}>
                        <td><b>{data.name || slug}</b></td>
                        <td>{data.count || 0}</td>
                        <td>
                          {data.worst_regression?.delta_pct 
                            ? `${data.worst_regression.delta_pct.toFixed(1)}% slower`
                            : 'N/A'}
                        </td>
                        <td>{data.worst_regression?.commit || 'N/A'}</td>
                      </tr>
                    ))
                  ) : (
                    <tr><td colSpan="4" style={{color: '#fff'}}>Loading...</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default GlobalMetrics;

