# Release Intelligence Platform

A read-only control plane that analyzes CI/CD data across repositories and provides actionable diagnostics. Synthesizes data from Bitbucket Pipelines, Jira, and SonarQube to answer: "Why did delivery slow down, where did it break, and what should we fix first?"

## Features

### Pinpoint Regressions
- ✅ **"Repo X slowed down 42% after commit Z"** - Identifies exact commit causing regression
- ✅ **"Step Y regressed across multiple repos"** - Cross-repo step-level analysis

### Cross-Repo Pattern Matching
- ✅ **"This failure matches a known pattern seen in 3 other repos"** - Failure pattern detection across repositories

### Core Metrics
- ✅ Build duration trends with regression detection
- ✅ Slow pipeline detection (baseline vs current)
- ✅ Build minutes per repo (cost optimization)
- ✅ PR velocity (median + P90)
- ✅ Deployment frequency per repo
- ✅ Failing pipeline alerts with parsed error summary
- ✅ Latest Docker images per environment per repository

### Resource Optimization
- ✅ Timeout waste detection: "Timeout is 4× higher than actual duration"
- ✅ Memory waste detection (when API provides data)

### AI-Powered Suggestions (Optional)
- Optional AI enhancement for actionable suggestions
- Works without AI using pattern matching and statistical analysis

## Architecture

- **Backend**: FastAPI (Python)
- **Database**: SQLite (can be upgraded to PostgreSQL)
- **Integrations**: Bitbucket Pipelines API, Jira API, SonarQube API
- **Frontend**: React dashboard
- **Analytics**: Time-series analysis, regression detection, pattern matching
- **AI**: Optional Hugging Face or OpenAI integration

## Quick Start

### Prerequisites

- Python 3.8+
- Node.js 14+ (for frontend)
- Access credentials for Bitbucket, Jira, and SonarQube

### Installation

1. **Install Python dependencies:**
```bash
pip install -r requirements.txt
```

2. **Configure environment variables:**
```bash
cp env.example .env
```

Edit `.env` with your credentials (Bitbucket and Jira can share the same Atlassian API token):
```bash
# Bitbucket
BITBUCKET_WORKSPACE=your-workspace
BITBUCKET_USERNAME=your-username
BITBUCKET_API_TOKEN=your-atlassian-token  # same token can be reused for Jira

# Jira
JIRA_URL=https://your-company.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-atlassian-token       # same token as above

# SonarQube
SONARQUBE_URL=https://sonarqube.your-company.com
SONARQUBE_TOKEN=your-sonarqube-token

# AI (Optional - see AI Configuration section)
AI_PROVIDER=huggingface  # or "openai" or "none"
USE_AI_SUGGESTIONS=true
HUGGINGFACE_API_KEY=  # Optional
```

3. **Initialize database:**
```bash
python scripts/init_db.py
```

4. **Start the API server:**
```bash
uvicorn app.main:app --reload
```

API will be available at `http://localhost:8000`

5. **Start data collection (in separate terminal):**
```bash
python scripts/collector.py
```

This collects data every 15 minutes (configurable via `COLLECTION_INTERVAL_MINUTES`).

6. **Generate diagnostics:**
```bash
curl -X POST http://localhost:8000/api/collect
curl -X POST http://localhost:8000/api/diagnostics/generate
```

7. **Start frontend (optional):**
```bash
cd frontend
npm install
npm start
```

Frontend will be available at `http://localhost:3000`

### Windows Quick Start

Use the provided batch file:
```cmd
run.bat
```

This starts both the API and collector automatically.

## Testing Without Real Data

For testing without Bitbucket access, use mock data:

```bash
python scripts/seed_mock_data.py
curl -X POST http://localhost:8000/api/diagnostics/generate
```

This populates the database with sample builds, PRs, and deployments.

## API Endpoints

### Repositories
- `GET /api/repositories` - List all repositories
- `GET /api/repositories/{id}/build-duration-trends` - Build duration trends over time
- `GET /api/repositories/{id}/pr-velocity` - PR velocity metrics (median + P90)
- `GET /api/repositories/{id}/deployment-frequency` - Deployment frequency
- `GET /api/repositories/{id}/build-minutes` - Total build minutes consumed
- `GET /api/repositories/{id}/slow-pipelines` - Slow pipeline detection
- `GET /api/repositories/{id}/latest-images` - Latest Docker images per environment
- `GET /api/repositories/{id}/regressions` - Regression analysis

### Diagnostics
- `GET /api/diagnostics` - Get all actionable diagnostics
- `POST /api/diagnostics/generate` - Generate new diagnostics

### Data Collection
- `POST /api/collect` - Trigger manual data collection

### Summary
- `GET /api/metrics/summary` - Summary metrics across all repositories

### API Documentation

Once server is running:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## AI Configuration

The platform works without AI using pattern matching and statistical analysis. Optional AI adds enhanced suggestions.

### Option 1: Hugging Face (Recommended - Free)

1. Get free API token (optional): https://huggingface.co/settings/tokens
2. Configure in `.env`:
```bash
AI_PROVIDER=huggingface
USE_AI_SUGGESTIONS=true
HUGGINGFACE_API_KEY=your_token_here  # Optional
```

### Option 2: OpenAI (Free Tier Available)

1. Get API key: https://platform.openai.com/api-keys
2. Configure in `.env`:
```bash
AI_PROVIDER=openai
USE_AI_SUGGESTIONS=true
OPENAI_API_KEY=sk-...
```

### Option 3: Disable AI

```bash
AI_PROVIDER=none
USE_AI_SUGGESTIONS=false
```

**What AI adds:**
- Without AI: "Repo X slowed 42% after commit Z"
- With AI: "Repo X slowed 42% after commit Z. 💡 Suggestion: Check commit diff for new dependencies or build config changes."

## Project Structure

```
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Configuration management
│   ├── database.py             # Database connection
│   ├── models.py               # SQLAlchemy models
│   ├── collector.py            # Data collection orchestrator
│   ├── diagnostics.py          # Diagnostic engine
│   ├── integrations/
│   │   ├── bitbucket.py        # Bitbucket API client
│   │   ├── jira.py             # Jira API client
│   │   └── sonarqube.py        # SonarQube API client
│   ├── analytics/
│   │   ├── metrics_calculator.py    # Metrics calculations
│   │   ├── regression_detector.py  # Regression detection
│   │   └── pattern_matcher.py      # Pattern matching
│   └── ai/
│       └── suggestion_generator.py  # AI suggestion generator
├── frontend/
│   ├── src/
│   │   ├── App.js              # Main React component
│   │   └── components/        # React components
│   └── package.json
├── scripts/
│   ├── init_db.py              # Database initialization
│   ├── collector.py            # Scheduled data collector
│   └── seed_mock_data.py       # Mock data generator
├── requirements.txt            # Python dependencies
├── .env.example               # Environment variables template
└── README.md                   # This file
```

## Data Flow

1. **Collection**: `collector.py` runs periodically (default: 15 minutes)
   - Fetches repositories from Bitbucket
   - Collects pipeline builds and steps
   - Collects pull requests
   - Collects deployment information
   - Stores in SQLite database

2. **Analysis**: `DiagnosticEngine` generates insights
   - Regression detection compares baseline (14 days ago) vs recent builds
   - Pattern matching identifies recurring failures across repos
   - Resource waste detection finds over-provisioned steps

3. **API**: FastAPI serves metrics and diagnostics
   - REST endpoints for all metrics
   - Real-time data queries
   - Diagnostic generation on-demand

4. **Visualization**: React dashboard displays
   - Build duration trends
   - PR velocity metrics
   - Deployment frequency
   - Actionable diagnostics

## Database Schema

- **Repositories**: Core repository information
- **Builds**: Pipeline execution records with duration, state, commit hash
- **BuildSteps**: Individual step execution with timing and resource usage
- **PullRequests**: PR tracking for velocity calculations
- **Deployments**: Deployment records with environment and Docker image
- **BuildFailures**: Failure records with normalized error patterns
- **Diagnostics**: Generated actionable insights

## Example Diagnostics

The platform generates actionable diagnostics like:

- **Regression**: "Repo user-service slowed down 42% after commit abc12345"
- **Cross-repo**: "Step 'run-tests' regressed across 3 repositories"
- **Pattern Match**: "This failure matches a known pattern seen in 5 other builds across 2 repositories"
- **Resource Waste**: "Step 'build-docker' has timeout 4× higher than actual duration (300s timeout vs 75s actual)"
- **Slow Pipeline**: "Build #1234 is 2.3× slower than P90 threshold"

## Troubleshooting

### Database Issues
- Ensure `scripts/init_db.py` ran successfully
- Check file permissions on `release_intelligence.db`

### API Connection Issues
- Verify credentials in `.env` are correct
- Check Bitbucket/Jira/SonarQube API access
- Ensure ports 8000 (API) and 3000 (frontend) are not in use

### No Data Showing
1. Run data collection: `curl -X POST http://localhost:8000/api/collect`
2. Wait for collection to complete (may take several minutes)
3. Generate diagnostics: `curl -X POST http://localhost:8000/api/diagnostics/generate`
4. Check that repositories exist in Bitbucket workspace

### Frontend Not Connecting
- Ensure API is running on port 8000
- Check browser console for CORS errors
- Verify `REACT_APP_API_URL` in frontend/.env (if using custom URL)

### Collection Errors
- Verify your credentials in `.env` have proper permissions
- Check Bitbucket workspace name is correct
- Ensure API tokens are valid

### AI Not Working
- AI is optional - platform works without it
- Check `AI_PROVIDER` setting in `.env`
- Verify API keys if using OpenAI or Hugging Face
- Falls back gracefully if AI unavailable

## Development

### Running Tests

Test individual features:

```bash
# Test regression detection
curl -X POST http://localhost:8000/api/diagnostics/generate
curl http://localhost:8000/api/diagnostics

# Test metrics
curl http://localhost:8000/api/repositories/1/pr-velocity
curl http://localhost:8000/api/repositories/1/build-duration-trends
curl http://localhost:8000/api/repositories/1/slow-pipelines
```

### Adding New Integrations

1. Create client in `app/integrations/`
2. Add data collection in `app/collector.py`
3. Add models in `app/models.py` if needed
4. Add API endpoints in `app/main.py`

### Customizing Analytics

- Modify `app/analytics/regression_detector.py` for regression thresholds
- Update `app/analytics/pattern_matcher.py` for pattern matching logic
- Adjust `app/diagnostics.py` for diagnostic message formatting

## Production Deployment

For production:
1. Upgrade to PostgreSQL (change `DATABASE_URL` in `.env`)
2. Use production WSGI server (gunicorn)
3. Set up proper authentication/authorization
4. Configure HTTPS
5. Set up monitoring and logging
6. Use environment-specific configuration

## License

This project is built for hackathon demonstration purposes.

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review API documentation at `/docs` endpoint
3. Check logs for detailed error messages
