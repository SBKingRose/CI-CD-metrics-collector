import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';
import MetricsDashboard from './components/MetricsDashboard';
import DiagnosticsPanel from './components/DiagnosticsPanel';
import RepositorySelector from './components/RepositorySelector';
import GlobalMetrics from './components/GlobalMetrics';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function App() {
  const [repositories, setRepositories] = useState([]);
  const [selectedRepo, setSelectedRepo] = useState(null);
  const [diagnostics, setDiagnostics] = useState([]);
  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(true);

  useEffect(() => {
    loadRepositories();
    loadDiagnostics();
    loadSummary();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // load once on mount

  const loadRepositories = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/repositories`);
      setRepositories(response.data);
      if (response.data.length > 0 && !selectedRepo) {
        setSelectedRepo(response.data[0].id);
      }
    } catch (error) {
      console.error('Error loading repositories:', error);
    }
  };

  const loadDiagnostics = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/diagnostics`);
      setDiagnostics(response.data);
    } catch (error) {
      console.error('Error loading diagnostics:', error);
    }
  };

  const loadSummary = async () => {
    try {
      const [summaryResp, buildStatsResp] = await Promise.all([
        axios.get(`${API_BASE}/api/metrics/summary`),
        axios.get(`${API_BASE}/api/metrics/build-stats-file`)
      ]);
      const merged = Object.assign({}, summaryResp.data, { build_stats: buildStatsResp.data });
      setSummary(merged);
    } catch (error) {
      console.error('Error loading summary metrics:', error);
    }
    setSummaryLoading(false);
  };

  const triggerCollection = async () => {
    try {
      await axios.post(`${API_BASE}/api/collect`);
      await axios.post(`${API_BASE}/api/diagnostics/generate`);
      loadDiagnostics();
      alert('Data collection and diagnostics generation completed');
    } catch (error) {
      alert('Error triggering collection: ' + error.message);
    }
  };

  return (
    <div className="App container-fluid p-3">
      <header className="App-header d-flex align-items-center justify-content-between mb-3">
        <h1 className="h4 mb-0">Release Intelligence Platform</h1>
        <div>
          <button onClick={triggerCollection} className="btn btn-primary btn-sm me-2">
            Collect Data & Generate Diagnostics
          </button>
        </div>
      </header>

      <div className="App-content row">
        <div className="sidebar col-md-3">
          <RepositorySelector
            repositories={repositories}
            selectedRepo={selectedRepo}
            onSelect={setSelectedRepo}
          />
        </div>

        <div className="main-content col-md-9">
          <GlobalMetrics summary={summary} loading={summaryLoading} repositories={repositories} />
          {selectedRepo && (
            <MetricsDashboard repositoryId={selectedRepo} repositories={repositories} />
          )}
          <div className="mt-4">
            <DiagnosticsPanel diagnostics={diagnostics} />
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;

