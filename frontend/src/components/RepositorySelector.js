import React from 'react';
import './RepositorySelector.css';

function RepositorySelector({ repositories, selectedRepo, onSelect }) {
  return (
    <div className="card">
      <h2>Repositories</h2>
      <ul className="repo-list">
        {repositories.map(repo => (
          <li
            key={repo.id}
            className={`repo-item ${selectedRepo === repo.id ? 'active' : ''}`}
            onClick={() => onSelect(repo.id)}
          >
            {repo.name}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default RepositorySelector;

