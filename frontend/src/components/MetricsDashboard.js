import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import './MetricsDashboard.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function MetricsDashboard({ repositoryId, repositories = [] }) {
  const [metrics, setMetrics] = useState(null);
  const [trends, setTrends] = useState([]);
  const [loading, setLoading] = useState(true);
  const [latestImages, setLatestImages] = useState({});
  const [slowPipelines, setSlowPipelines] = useState([]);
  const [recentFailures, setRecentFailures] = useState([]);
  const [devSlowdown, setDevSlowdown] = useState(null);
  const [vulns, setVulns] = useState(null);
  const [resource, setResource] = useState(null);
  const [buildStats, setBuildStats] = useState(null);
  const [latestDeployment, setLatestDeployment] = useState(null);
  const [last5Pipelines, setLast5Pipelines] = useState([]);
  const [buildNumbersByEnv, setBuildNumbersByEnv] = useState(null);
  const [slowPipelineAnalysis, setSlowPipelineAnalysis] = useState(null);
  const [pipelineComparisons, setPipelineComparisons] = useState(null);
  const [lastPipelineDeploymentTime, setLastPipelineDeploymentTime] = useState(null);
  const [latestFailureAnalysis, setLatestFailureAnalysis] = useState(null);

  // Define all load functions before useEffect
  const loadLastPipelineDeploymentTime = async () => {
    if (!repositoryId) return;
    try {
      const response = await axios.get(`${API_BASE}/api/repositories/${repositoryId}/last-pipeline-deployment-time`);
      setLastPipelineDeploymentTime(response.data);
    } catch (error) {
      console.error('Error loading last pipeline deployment time:', error);
    }
  };

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
      loadBuildStats();
      loadLatestDeployment();
      loadLast5Pipelines();
      loadBuildNumbersByEnv();
      loadSlowPipelineAnalysis();
      loadPipelineComparisons();
      loadLatestFailureAnalysis();
      loadLastPipelineDeploymentTime();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repositoryId, repositories]);

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
      const repo = repositories.find(r => r.id === repositoryId);
      if (!repo) return;
      const repoSlug = repo.slug;
      const response = await axios.get(`${API_BASE}/api/vulnerabilities/${repoSlug}`);
      setVulns(response.data);
    } catch (error) {
      console.error('Error loading vulnerabilities:', error);
      setVulns({ repo: '', vulnerabilities: [], cross_repo: {} });
    }
  };

  const loadResource = async () => {
    try {
      const repo = repositories.find(r => r.id === repositoryId);
      if (!repo) return;
      const repoSlug = repo.slug;
      const response = await axios.get(`${API_BASE}/api/resource-usage/${repoSlug}`);
      setResource(response.data);
    } catch (error) {
      console.error('Error loading resource usage:', error);
    }
  };

  const loadBuildStats = async () => {
    try {
      const repo = repositories.find(r => r.id === repositoryId);
      if (!repo) return;
      const repoSlug = repo.slug;
      const response = await axios.get(`${API_BASE}/api/repositories/${repoSlug}/build-stats`);
      setBuildStats(response.data);
    } catch (error) {
      console.error('Error loading build stats:', error);
    }
  };

  const loadLatestDeployment = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/repositories/${repositoryId}/latest-deployment`);
      setLatestDeployment(response.data);
    } catch (error) {
      console.error('Error loading latest deployment:', error);
    }
  };

  const loadLast5Pipelines = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/repositories/${repositoryId}/last-5-pipelines`);
      setLast5Pipelines(response.data || []);
    } catch (error) {
      console.error('Error loading last 5 pipelines:', error);
      setLast5Pipelines([]);
    }
  };

  const loadBuildNumbersByEnv = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/repositories/${repositoryId}/build-numbers-by-environment`);
      setBuildNumbersByEnv(response.data);
    } catch (error) {
      console.error('Error loading build numbers by environment:', error);
    }
  };

  const loadSlowPipelineAnalysis = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/repositories/${repositoryId}/slow-pipeline-analysis`);
      setSlowPipelineAnalysis(response.data);
    } catch (error) {
      console.error('Error loading slow pipeline analysis:', error);
    }
  };

  const loadPipelineComparisons = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/repositories/${repositoryId}/pipeline-comparisons`);
      setPipelineComparisons(response.data);
    } catch (error) {
      console.error('Error loading pipeline comparisons:', error);
    }
  };

  const loadLatestFailureAnalysis = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/repositories/${repositoryId}/latest-failure-analysis-by-id`);
      setLatestFailureAnalysis(response.data);
    } catch (error) {
      console.error('Error loading latest failure analysis:', error);
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
              {buildStats?.build_minutes_decimal 
                ? buildStats.build_minutes_decimal.toFixed(2)
                : (metrics.buildMinutes?.total_minutes?.toFixed(0) || 0)}
            </div>
            <div className="metric-sublabel">
              {buildStats?.build_minutes_decimal ? 'From build_stats.json' : 'Last 30 days'}
            </div>
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
                <div className="metric-sublabel">Slow if &gt; P90</div>
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

      <div className="card">
        <h2>Resource Usage (CPU & Memory)</h2>
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

      <div className="card">
        <h2>Vulnerability Report</h2>
        {!vulns ? (
          <div className="empty-state">Loading vulnerabilities...</div>
        ) : vulns.error ? (
          <div className="text-danger">
            <div><strong>Error:</strong> {vulns.error}</div>
            {vulns.searched_path && <div className="small mt-2">Searched path: {vulns.searched_path}</div>}
            {vulns.repo_slug && <div className="small">Repo slug: {vulns.repo_slug}</div>}
            {vulns.repo_name && <div className="small">Repo name: {vulns.repo_name}</div>}
          </div>
        ) : (
          <div>
            {vulns.vulnerabilities && vulns.vulnerabilities.length > 0 ? (
              <div>
                <div className="mb-3">Found <b>{vulns.vulnerabilities.length}</b> vulnerabilities:</div>
                <div className="table-responsive">
                  <table className="table table-dark table-striped">
                    <thead>
                      <tr>
                        <th>Library</th>
                        <th>CVE</th>
                        <th>Severity</th>
                        <th>Status</th>
                        <th>Installed</th>
                        <th>Fixed</th>
                        <th>Cross-Repo</th>
                      </tr>
                    </thead>
                    <tbody>
                      {vulns.vulnerabilities.map((v, idx) => (
                        <tr key={idx}>
                          <td><b>{v.library || v.package}</b></td>
                          <td>
                            {v.cve || v.id}
                            {v.url && <a href={v.url} target="_blank" rel="noopener noreferrer" className="ms-1">🔗</a>}
                          </td>
                          <td>
                            <span className={`badge ${
                              v.severity === 'CRITICAL' ? 'bg-danger' :
                              v.severity === 'HIGH' ? 'bg-warning' :
                              v.severity === 'MEDIUM' ? 'bg-info' : 'bg-secondary'
                            }`}>
                              {v.severity}
                            </span>
                          </td>
                          <td>{v.status || 'unknown'}</td>
                          <td>{v.installed_version || 'N/A'}</td>
                          <td>{v.fixed_version || 'N/A'}</td>
                          <td>
                            {v.cross_repo_count > 0 ? (
                              <span className="text-warning" title={v.cross_repo_names?.join(', ')}>
                                Also in {v.cross_repo_count} repo{v.cross_repo_count > 1 ? 's' : ''}: {v.cross_repo_names?.join(', ')}
                              </span>
                            ) : (
                              <span className="text-muted">—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <div className="text-success">No vulnerabilities found.</div>
            )}
          </div>
        )}
      </div>

      {buildStats && !buildStats.error && (
        <div className="card">
          <h2>Build Statistics</h2>
          <div className="row">
            <div className="col-md-3">
              <div className="metric-card">
                <div className="metric-label">Total Builds</div>
                <div className="metric-value">{buildStats.builds || 0}</div>
              </div>
            </div>
            <div className="col-md-3">
              <div className="metric-card">
                <div className="metric-label">Build Duration</div>
                <div className="metric-value" style={{fontSize: '0.9rem'}}>{buildStats.build_duration || 'N/A'}</div>
              </div>
            </div>
            <div className="col-md-3">
              <div className="metric-card">
                <div className="metric-label">Build Minutes Used</div>
                <div className="metric-value" style={{fontSize: '0.9rem'}}>{buildStats.build_minutes_used || 'N/A'}</div>
                {buildStats.build_minutes_decimal && (
                  <div className="metric-sublabel">({buildStats.build_minutes_decimal.toFixed(2)} minutes)</div>
                )}
              </div>
            </div>
            <div className="col-md-3">
              {lastPipelineDeploymentTime && lastPipelineDeploymentTime.last_deployment_time && (
                <div className="metric-card">
                  <div className="metric-label">Last Pipeline Deployment</div>
                  <div className="metric-value" style={{fontSize: '0.9rem'}}>
                    {new Date(lastPipelineDeploymentTime.last_deployment_time).toLocaleString()}
                  </div>
                  <div className="metric-sublabel">Build #{lastPipelineDeploymentTime.build_number}</div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Last 5 Pipelines Status */}
      <div className="card">
        <h2>Last 5 Pipelines Status</h2>
        {last5Pipelines.length === 0 ? (
          <div className="empty-state" style={{color:'#fff'}}>No pipeline data available.</div>
        ) : (
          <div className="table-responsive">
            <table className="table table-dark table-striped">
              <thead>
                <tr>
                  <th>Build #</th>
                  <th>State</th>
                  <th>Commit</th>
                  <th>Duration</th>
                  <th>Failed Step</th>
                  <th>Error Summary</th>
                  <th>Cross-Repo</th>
                  <th>Log</th>
                </tr>
              </thead>
              <tbody>
                {last5Pipelines.map((p, idx) => (
                  <tr key={idx}>
                    <td>#{p.build_number || p.build_id}</td>
                    <td>
                      <span className={`badge ${
                        p.state === 'SUCCESSFUL' ? 'bg-success' :
                        p.state === 'FAILED' || p.state === 'ERROR' ? 'bg-danger' :
                        'bg-warning'
                      }`}>
                        {p.state}
                      </span>
                    </td>
                    <td>{p.commit_hash ? p.commit_hash.substring(0, 8) : 'N/A'}</td>
                    <td>{p.duration_seconds ? `${p.duration_seconds.toFixed(1)}s` : 'N/A'}</td>
                    <td>{p.failed_step || '—'}</td>
                    <td className="text-truncate" style={{maxWidth: '300px'}} title={p.error_message}>
                      {p.error_message || '—'}
                    </td>
                    <td>
                      {p.cross_repo_count > 0 ? (
                        <span className="text-warning">
                          Also in {p.cross_repo_count} repo{p.cross_repo_count > 1 ? 's' : ''}
                        </span>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td>
                      {p.log_url && (
                        <a href={p.log_url} target="_blank" rel="noopener noreferrer" className="btn btn-sm btn-outline-light">
                          View
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Build Numbers by Environment */}
      {buildNumbersByEnv && buildNumbersByEnv.by_environment && (
        <div className="card">
          <h2>Build Numbers Deployed by Environment</h2>
          <div className="table-responsive">
            <table className="table table-dark table-striped">
              <thead>
                <tr>
                  <th>Environment</th>
                  <th>Build Number</th>
                  <th>Commit</th>
                  <th>Deployed At</th>
                </tr>
              </thead>
              <tbody>
                {Object.values(buildNumbersByEnv.by_environment).map((env, idx) => (
                  <tr key={idx}>
                    <td><b>{env.environment}</b></td>
                    <td>#{env.build_number || 'N/A'}</td>
                    <td>{env.commit_hash ? env.commit_hash.substring(0, 8) : 'N/A'}</td>
                    <td>{env.deployed_at ? new Date(env.deployed_at).toLocaleString() : 'N/A'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Slow Pipeline Analysis - Always show this section */}
      <div className="card">
        <h2>Slow Pipeline Analysis</h2>
        {!slowPipelineAnalysis ? (
          <div className="empty-state" style={{color:'#fff'}}>Loading slow pipeline analysis...</div>
        ) : slowPipelineAnalysis.analysis && slowPipelineAnalysis.analysis.length > 0 ? (
          <div>
            <div className="mb-3" style={{color:'#fff'}}>{slowPipelineAnalysis.message}</div>
            <div className="table-responsive">
              <table className="table table-dark table-striped">
                <thead>
                  <tr>
                    <th>Analysis</th>
                    <th>Build #</th>
                    <th>Commit</th>
                    <th>Duration</th>
                    <th>Median</th>
                    <th>Slower By</th>
                    <th>Created At</th>
                  </tr>
                </thead>
                <tbody>
                  {slowPipelineAnalysis.analysis.map((analysis, idx) => (
                    <tr key={idx}>
                      <td><b>{analysis.message || `${slowPipelineAnalysis.repository_name} is slower by ${analysis.slower_by_pct.toFixed(1)}% after commit ${analysis.commit_hash ? analysis.commit_hash.substring(0, 8) : 'unknown'}`}</b></td>
                      <td>#{analysis.build_number || analysis.build_id}</td>
                      <td>{analysis.commit_hash ? analysis.commit_hash.substring(0, 8) : 'N/A'}</td>
                      <td>{analysis.duration_seconds ? `${analysis.duration_seconds.toFixed(1)}s` : 'N/A'}</td>
                      <td>{analysis.median_duration_seconds ? `${analysis.median_duration_seconds.toFixed(1)}s` : 'N/A'}</td>
                      <td className="text-warning">
                        {analysis.slower_by_pct > 0 ? `${analysis.slower_by_pct.toFixed(1)}%` : '—'}
                      </td>
                      <td>{analysis.created_at ? new Date(analysis.created_at).toLocaleString() : 'N/A'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="empty-state" style={{color:'#fff'}}>
            No slow pipelines detected. This requires build data from the last 14 days. 
            <br />
            <small>Run <code>python scripts/collector.py</code> to collect build data from Bitbucket.</small>
          </div>
        )}
      </div>

      {/* Pipeline Comparisons - Show all successful pipelines with comparison to previous */}
      <div className="card">
        <h2>Pipeline Duration Comparisons</h2>
        {!pipelineComparisons ? (
          <div className="empty-state" style={{color:'#fff'}}>Loading pipeline comparisons...</div>
        ) : pipelineComparisons.pipelines && pipelineComparisons.pipelines.length > 0 ? (
          <div>
            <div className="mb-3" style={{color:'#fff'}}>{pipelineComparisons.message}</div>
            <div className="table-responsive">
              <table className="table table-dark table-striped">
                <thead>
                  <tr>
                    <th>Build #</th>
                    <th>Commit</th>
                    <th>Duration</th>
                    <th>Previous Build</th>
                    <th>Previous Commit</th>
                    <th>Previous Duration</th>
                    <th>Comparison</th>
                    <th>Completed At</th>
                  </tr>
                </thead>
                <tbody>
                  {pipelineComparisons.pipelines.map((p, idx) => (
                    <tr key={idx}>
                      <td><b>#{p.build_number}</b></td>
                      <td><code>{p.commit_short}</code></td>
                      <td>
                        <b>{p.duration_minutes ? `${p.duration_minutes.toFixed(2)} min` : `${p.duration_seconds.toFixed(1)}s`}</b>
                        <div className="small text-muted">({p.duration_seconds.toFixed(1)}s)</div>
                      </td>
                      <td>{p.previous_build_number ? `#${p.previous_build_number}` : '—'}</td>
                      <td>{p.previous_commit ? <code>{p.previous_commit}</code> : '—'}</td>
                      <td>{p.previous_duration_seconds ? `${(p.previous_duration_seconds / 60).toFixed(2)} min (${p.previous_duration_seconds.toFixed(1)}s)` : '—'}</td>
                      <td>
                        {p.delta_pct !== null && p.delta_pct !== undefined ? (
                          <span className={p.delta_pct > 0 ? 'text-warning' : p.delta_pct < 0 ? 'text-success' : ''}>
                            {p.comparison}
                          </span>
                        ) : (
                          <span className="text-muted">{p.comparison}</span>
                        )}
                      </td>
                      <td>{p.completed_at ? new Date(p.completed_at).toLocaleString() : 'N/A'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="empty-state" style={{color:'#fff'}}>
            No successful pipelines found. This requires build data from Bitbucket.
            <br />
            <small>Run <code>python scripts/collector.py</code> to collect build data.</small>
          </div>
        )}
      </div>

      {/* Latest Failure Analysis */}
      <div className="card">
        <h2>Latest Pipeline Failure Analysis</h2>
        {!latestFailureAnalysis ? (
          <div className="empty-state" style={{color:'#fff'}}>Loading failure analysis...</div>
        ) : latestFailureAnalysis.status === "OK" ? (
          <div className="text-success" style={{color:'#00ff6a'}}>
            ✓ {latestFailureAnalysis.message}
          </div>
        ) : latestFailureAnalysis.status === "FAILED" ? (
          <div>
            <div className="mb-3">
              <div className="text-danger" style={{color:'#ff00ea'}}>
                <strong>Latest pipeline failed</strong>
              </div>
              <div style={{color:'#fff'}}>
                Build #{latestFailureAnalysis.build_number} • Commit {latestFailureAnalysis.commit_hash?.substring(0, 8) || 'N/A'}
              </div>
              {latestFailureAnalysis.completed_at && (
                <div className="small text-muted" style={{color:'#94a3b8'}}>
                  Failed at: {new Date(latestFailureAnalysis.completed_at).toLocaleString()}
                </div>
              )}
            </div>

            {/* Failed Steps */}
            {latestFailureAnalysis.failed_steps && latestFailureAnalysis.failed_steps.length > 0 && (
              <div className="mb-3">
                <h5 style={{color:'#fff'}}>Failed Steps:</h5>
                {latestFailureAnalysis.failed_steps.map((step, idx) => (
                  <div key={idx} className="mb-3 p-3" style={{background: 'rgba(255,0,234,0.1)', borderRadius: '8px'}}>
                    <div style={{color:'#fff'}}><strong>{step.step_name}</strong></div>
                    {step.error_signature && (
                      <div className="mt-2">
                        <div className="small" style={{color:'#94a3b8'}}>Error Signature:</div>
                        <pre style={{background: 'rgba(0,0,0,0.3)', padding: '10px', borderRadius: '4px', fontSize: '0.85rem', color:'#fff', maxHeight: '200px', overflow: 'auto'}}>
                          {step.error_signature}
                        </pre>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Known Fixes */}
            {latestFailureAnalysis.known_fixes && latestFailureAnalysis.known_fixes.length > 0 && (
              <div className="mb-3">
                <h5 style={{color:'#00ff6a'}}>Suggested Fixes:</h5>
                {latestFailureAnalysis.known_fixes.map((fix, idx) => (
                  <div key={idx} className="mb-3 p-3" style={{background: 'rgba(0,255,106,0.1)', borderRadius: '8px'}}>
                    <div style={{color:'#00ff6a'}}><strong>Cause:</strong> {fix.cause}</div>
                    <div className="mt-2" style={{color:'#fff'}}>
                      <strong>Fix:</strong>
                      <ul className="mt-2">
                        {fix.fix.map((f, i) => (
                          <li key={i}>{f}</li>
                        ))}
                      </ul>
                    </div>
                    {fix.link && (
                      <div className="mt-2">
                        <a href={fix.link} target="_blank" rel="noopener noreferrer" style={{color:'#00fff7'}}>
                          Learn more →
                        </a>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Cross-Repo Matches */}
            {latestFailureAnalysis.other_repos_count > 0 && (
              <div className="mb-3">
                <h5 style={{color:'#fffb00'}}>
                  This error was also seen in {latestFailureAnalysis.other_repos_count} other repositor{latestFailureAnalysis.other_repos_count > 1 ? 'ies' : 'y'}:
                </h5>
                <div className="table-responsive">
                  <table className="table table-dark table-striped table-sm">
                    <thead>
                      <tr>
                        <th>Repository</th>
                        <th>Build #</th>
                        <th>Occurred At</th>
                        <th>Error Excerpt</th>
                      </tr>
                    </thead>
                    <tbody>
                      {latestFailureAnalysis.other_repos_with_same_error.map((repo, idx) => (
                        <tr key={idx}>
                          <td><strong>{repo.repository_name || repo.repository_slug}</strong></td>
                          <td>#{repo.build_number}</td>
                          <td>{repo.occurred_at ? new Date(repo.occurred_at).toLocaleString() : 'N/A'}</td>
                          <td className="small">{repo.error_message || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {latestFailureAnalysis.other_repos_count === 0 && (
              <div className="text-muted" style={{color:'#94a3b8'}}>
                This error has not been seen in other repositories yet.
              </div>
            )}
          </div>
        ) : (
          <div className="empty-state" style={{color:'#fff'}}>
            {latestFailureAnalysis.message || "Unable to analyze failures"}
          </div>
        )}
      </div>

      {latestDeployment && latestDeployment.latest_deployment && (
        <div className="card neon-card">
          <h2 style={{color:'#fff'}}>Latest Deployment</h2>
          <div className="row">
            <div className="col-md-3">
              <div className="metric-card">
                <div className="metric-label" style={{color:'#fff'}}>Environment</div>
                <div className="metric-value" style={{color:'#fff'}}>{latestDeployment.latest_deployment.environment || 'N/A'}</div>
              </div>
            </div>
            <div className="col-md-3">
              <div className="metric-card">
                <div className="metric-label" style={{color:'#fff'}}>Build Number</div>
                <div className="metric-value" style={{color:'#fff'}}>#{latestDeployment.latest_deployment.build_number || 'N/A'}</div>
              </div>
            </div>
            <div className="col-md-3">
              <div className="metric-card">
                <div className="metric-label" style={{color:'#fff'}}>Commit</div>
                <div className="metric-value" style={{color:'#fff'}}>{latestDeployment.latest_deployment.commit_hash?.substring(0, 8) || 'N/A'}</div>
              </div>
            </div>
            <div className="col-md-3">
              <div className="metric-card">
                <div className="metric-label" style={{color:'#fff'}}>Deployed At</div>
                <div className="metric-value small" style={{color:'#fff'}}>
                  {latestDeployment.latest_deployment.deployed_at 
                    ? new Date(latestDeployment.latest_deployment.deployed_at).toLocaleString()
                    : 'N/A'}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default MetricsDashboard;

