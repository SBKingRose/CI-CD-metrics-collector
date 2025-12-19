import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import './MetricsDashboard.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function MetricsDashboard({ repositoryId }) {
  const [metrics, setMetrics] = useState(null);
  const [trends, setTrends] = useState([]);
  const [loading, setLoading] = useState(true);
  const [latestImages, setLatestImages] = useState({});
  const [slowPipelines, setSlowPipelines] = useState([]);
  const [recentFailures, setRecentFailures] = useState([]);
  const [devSlowdown, setDevSlowdown] = useState(null);
  const [vulns, setVulns] = useState(null);
  const [resource, setResource] = useState(null);

  useEffect(() => {
    if (repositoryId) {
      loadMetrics();
      loadTrends();
      loadLatestImages();
      loadSlowPipelines();
      loadRecentFailures();
      loadDevSlowdown();
      loadVulns();
      loadResource();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repositoryId]);

  const loadMetrics = async () => {
    try {
      const [prVelocity, deploymentFreq, buildMinutes, slowPipelines] = await Promise.all([
        axios.get(`${API_BASE}/api/repositories/${repositoryId}/pr-velocity`),
        axios.get(`${API_BASE}/api/repositories/${repositoryId}/deployment-frequency`),
        axios.get(`${API_BASE}/api/repositories/${repositoryId}/build-minutes`),
        axios.get(`${API_BASE}/api/repositories/${repositoryId}/slow-pipelines`)
      ]);

      setMetrics({
        prVelocity: prVelocity.data,
        deploymentFrequency: deploymentFreq.data,
        buildMinutes: buildMinutes.data,
        slowPipelines: slowPipelines.data
      });
    } catch (error) {
      console.error('Error loading metrics:', error);
    }
    setLoading(false);
  };

  const loadTrends = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/repositories/${repositoryId}/build-duration-trends`);
      setTrends(response.data);
    } catch (error) {
      console.error('Error loading trends:', error);
    }
  };

  const loadLatestImages = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/repositories/${repositoryId}/latest-images`);
      setLatestImages(response.data);
    } catch (error) {
      console.error('Error loading images:', error);
    }
  };

  const loadSlowPipelines = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/repositories/${repositoryId}/slow-pipelines`);
      setSlowPipelines(response.data || []);
    } catch (error) {
      console.error('Error loading slow pipelines:', error);
    }
  };

  const loadRecentFailures = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/repositories/${repositoryId}/recent-failures`);
      setRecentFailures(response.data || []);
    } catch (error) {
      console.error('Error loading recent failures:', error);
    }
  };

  const loadDevSlowdown = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/repositories/${repositoryId}/dev-deploy-slowdown`);
      setDevSlowdown(response.data);
    } catch (error) {
      console.error('Error loading dev deploy slowdown:', error);
    }
  };

  const loadVulns = async () => {
    try {
      // For demo, use repo name from repositories list
      let repoSlug = '';
      if (window && window.repositories && repositoryId) {
        const repo = window.repositories.find(r => r.id === repositoryId);
        repoSlug = repo ? repo.slug || repo.name : '';
      }
      // fallback for demo
      if (!repoSlug) repoSlug = 'woundhub';
      const response = await axios.get(`${API_BASE}/api/vulnerabilities/${repoSlug}`);
      setVulns(response.data);
    } catch (error) {
      setVulns({ error: error.message });
    }
  };

  const loadResource = async () => {
    try {
      let repoSlug = '';
      if (window && window.repositories && repositoryId) {
        const repo = window.repositories.find(r => r.id === repositoryId);
        repoSlug = repo ? repo.slug || repo.name : '';
      }
      if (!repoSlug) repoSlug = 'woundhub';
      const response = await axios.get(`${API_BASE}/api/resource-usage/${repoSlug}`);
      setResource(response.data);
    } catch (error) {
      setResource({ error: error.message });
    }
  };

  if (loading) {
    return <div className="loading">Loading metrics...</div>;
  }

  if (!metrics) {
    return <div className="loading">No metrics available</div>;
  }

  return (
    <div className="metrics-dashboard">
      <div className="card">
        <h2>Key Metrics</h2>
        <div className="metric-grid">
          <div className="metric-card">
            <div className="metric-label">PR Velocity (Median)</div>
            <div className="metric-value">
              {metrics.prVelocity?.median_hours 
                ? `${metrics.prVelocity.median_hours.toFixed(1)}h`
                : 'N/A'}
            </div>
            <div className="metric-sublabel">P90: {metrics.prVelocity?.p90_hours?.toFixed(1)}h</div>
          </div>

          <div className="metric-card">
            <div className="metric-label">Deployment Frequency</div>
            <div className="metric-value">
              {metrics.deploymentFrequency?.count || 0}
            </div>
            <div className="metric-sublabel">Last 30 days</div>
          </div>

          <div className="metric-card">
            <div className="metric-label">Build Minutes</div>
            <div className="metric-value">
              {metrics.buildMinutes?.total_minutes?.toFixed(0) || 0}
            </div>
            <div className="metric-sublabel">Last 30 days</div>
          </div>

          <div className="metric-card">
            <div className="metric-label">Slow Pipelines</div>
            <div className="metric-value">
              {metrics.slowPipelines?.length || 0}
            </div>
            <div className="metric-sublabel">Above P90 threshold</div>
          </div>
        </div>
        <details className="how-calculated">
          <summary>How these are calculated</summary>
          <div className="how-body">
            <div><b>PR velocity</b>: time from PR creation to merge. Median + P90 over last 30 days.</div>
            <div><b>Deployment frequency</b>: count of deployments recorded in last 30 days (best-effort from pipeline deployment steps / deployments API).</div>
            <div><b>Build minutes</b>: sum of pipeline duration (minutes) for completed builds in last 30 days (not yet weighted by step size).</div>
            <div><b>Slow pipelines</b>: builds whose duration is above P90 of the last 14 days; shows delta vs median.</div>
          </div>
        </details>
      </div>

      <div className="card">
        <h2>Dev Deploy Slowdown (main branch)</h2>
        {!devSlowdown ? (
          <div className="empty-state">
            Not enough successful `main` builds in the last 14 days to compute baseline.
          </div>
        ) : (
          <div className="dev-slowdown">
            <div className="metric-grid">
              <div className="metric-card">
                <div className="metric-label">Latest build duration</div>
                <div className="metric-value">{devSlowdown.latest.duration_seconds.toFixed(1)}s</div>
                <div className="metric-sublabel">Commit {devSlowdown.latest.commit_hash?.substring(0, 8)}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">Baseline median (14d)</div>
                <div className="metric-value">{devSlowdown.baseline.median_seconds.toFixed(1)}s</div>
                <div className="metric-sublabel">P90: {devSlowdown.baseline.p90_seconds.toFixed(1)}s</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">Delta vs median</div>
                <div className="metric-value">
                  {devSlowdown.delta.latest_vs_median_pct === null ? '—' : devSlowdown.delta.latest_vs_median_pct.toFixed(1) + '%'}
                </div>
                <div className="metric-sublabel">Slow if > P90</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">Delta vs previous</div>
                <div className="metric-value">
                  {devSlowdown.delta.latest_vs_prev_pct === null ? '—' : devSlowdown.delta.latest_vs_prev_pct.toFixed(1) + '%'}
                </div>
                <div className="metric-sublabel">Previous commit {devSlowdown.previous?.commit_hash?.substring(0, 8) || '—'}</div>
              </div>
            </div>
            <details className="how-calculated">
              <summary>Details</summary>
              <div className="how-body">
                <div><b>Median</b> = 50th percentile of successful `main` builds in the last 14 days.</div>
                <div><b>P90</b> = 90th percentile of the same window (threshold for “slow”).</div>
                <div><b>Latest vs previous</b> compares the last successful `main` build to the one before it.</div>
              </div>
            </details>
          </div>
        )}
      </div>

      <div className="card">
        <h2>Build Duration Trends</h2>
        {trends.length === 0 ? (
          <div className="empty-state">
            No trend data yet. This populates after collecting successful builds with completion times.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trends}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="median_duration" stroke="#8884d8" name="Median Duration (s)" />
              <Line type="monotone" dataKey="p90_duration" stroke="#82ca9d" name="P90 Duration (s)" />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="card">
        <h2>Latest Docker Images by Environment</h2>
        {Object.keys(latestImages).length === 0 ? (
          <div className="empty-state">
            No deployment/image data yet. This requires Bitbucket Deployments data or pipeline steps tagged with deployment environments.
          </div>
        ) : (
          <div className="images-list">
            {Object.entries(latestImages).map(([env, data]) => (
              <div key={env} className="image-item">
                <div className="image-env">{env}</div>
                <div className="image-name">{data.docker_image || 'N/A'}</div>
                <div className="image-meta">
                  {data.deployed_at && new Date(data.deployed_at).toLocaleDateString()}
                  {data.commit_hash && ` • ${data.commit_hash.substring(0, 8)}`}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <h2>Slow Pipelines (above P90)</h2>
        {slowPipelines.length === 0 ? (
          <div className="empty-state">
            No slow pipelines detected in the last 14 days for this repo (or insufficient successful builds to compute P90).
          </div>
        ) : (
          <div className="table">
            <div className="table-head">
              <div>Build</div>
              <div>Duration (s)</div>
              <div>Median (s)</div>
              <div>Delta vs Median</div>
              <div>Commit</div>
              <div>Completed</div>
            </div>
            {slowPipelines.map(sp => (
              <div key={sp.build_id} className="table-row">
                <div>#{sp.build_id}</div>
                <div>{sp.duration_seconds.toFixed(1)}</div>
                <div>{sp.baseline_median.toFixed(1)}</div>
                <div>{sp.delta_vs_median_pct ? sp.delta_vs_median_pct.toFixed(1) + '%' : '—'}</div>
                <div>{sp.commit_hash ? sp.commit_hash.substring(0, 8) : '—'}</div>
                <div>{sp.completed_at ? new Date(sp.completed_at).toLocaleString() : '—'}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <h2>Recent Pipeline Failures</h2>
        {recentFailures.length === 0 ? (
          <div className="empty-state">
            No failures recorded yet. Failure summaries require failed builds and step error messages/logs.
          </div>
        ) : (
          <div className="table">
            <div className="table-head">
              <div>Build</div>
              <div>Step</div>
              <div>Commit</div>
              <div>Error (truncated)</div>
              <div>Completed</div>
            </div>
            {recentFailures.map(f => (
              <div key={f.build_id} className="table-row">
                <div>#{f.build_id}</div>
                <div>{f.step || 'N/A'}</div>
                <div>{f.commit_hash ? f.commit_hash.substring(0, 8) : '—'}</div>
                <div className="truncate">{f.error_message || 'No error message'}</div>
                <div>{f.completed_at ? new Date(f.completed_at).toLocaleString() : '—'}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card neon-card">
        <h2 style={{color:'#fff'}}>Resource Usage (CPU & Memory)</h2>
        {!resource ? (
          <div className="empty-state" style={{color:'#fff'}}>Loading resource usage...</div>
        ) : resource.error ? (
          <div className="text-danger" style={{color:'#ff00ea'}}>{resource.error}</div>
        ) : (
          <div>
            <div style={{color:'#00fff7'}}>CPU Utilization: <b style={{color:'#fff'}}>{resource.cpu_utilization_pct}%</b></div>
            <div style={{color:'#00fff7'}}>Memory Utilization: <b style={{color:'#fff'}}>{resource.memory_utilization_pct}%</b></div>
            <div style={{color:'#fffb00'}}>Memory Limit: <b style={{color:'#fff'}}>{resource.memory_limit_mb} MB</b></div>
            <div style={{color:'#fffb00'}}>Memory Peak: <b style={{color:'#fff'}}>{resource.memory_peak_mb} MB</b></div>
            <div className="mt-2" style={{color:'#00ff6a'}}>{resource.recommendation}</div>
          </div>
        )}
      </div>

      <div className="card neon-card">
        <h2 style={{color:'#fff'}}>Vulnerability Report</h2>
        {!vulns ? (
          <div className="empty-state" style={{color:'#fff'}}>Loading vulnerabilities...</div>
        ) : vulns.error ? (
          <div className="text-danger" style={{color:'#ff00ea'}}>{vulns.error}</div>
        ) : (
          <div>
            {vulns.vulnerabilities && vulns.vulnerabilities.length > 0 ? (
              <div>
                <div className="mb-2" style={{color:'#fff'}}>Found <b>{vulns.vulnerabilities.length}</b> vulnerabilities:</div>
                <ul>
                  {vulns.vulnerabilities.map((v, idx) => (
                    <li key={idx} style={{color:'#fff'}}>
                      <b>{v.library}</b> <span className="badge bg-danger">{v.severity}</span> <a href={v.url} target="_blank" rel="noopener noreferrer" style={{color:'#00fff7'}}>{v.cve}</a><br/>
                      {v.title}<br/>
                      Installed: {v.installed_version}, Fixed: {v.fixed_version}
                    </li>
                  ))}
                </ul>
                {vulns.cross_repo && vulns.cross_repo.length > 0 && (
                  <div className="mt-2" style={{color:'#fffb00'}}>This vulnerability also observed in: {vulns.cross_repo.join(', ')}</div>
                )}
              </div>
            ) : (
              <div className="text-success" style={{color:'#00ff6a'}}>No vulnerabilities found.</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default MetricsDashboard;

