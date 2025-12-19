"""
Seed database with mock data for testing without Bitbucket access
"""
import sys
from pathlib import Path

# Add parent directory to path so we can import app
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta, timezone
import random
from app.database import SessionLocal, engine
from app.models import Base, Repository, Build, BuildStep, PullRequest, Deployment, BuildFailure
from app.analytics.pattern_matcher import PatternMatcher

# Create tables
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# Create sample repositories
repos_data = [
    {"name": "user-service", "slug": "user-service"},
    {"name": "payment-service", "slug": "payment-service"},
    {"name": "api-gateway", "slug": "api-gateway"},
]

repositories = []
for repo_data in repos_data:
    repo = db.query(Repository).filter(Repository.slug == repo_data["slug"]).first()
    if not repo:
        repo = Repository(
            name=repo_data["name"],
            slug=repo_data["slug"],
            workspace="test-workspace"
        )
        db.add(repo)
        db.flush()
    repositories.append(repo)

db.commit()

# Generate mock builds
step_names = ["install-dependencies", "run-tests", "build-docker", "deploy-staging"]
error_patterns = [
    "timeout after 300 seconds",
    "out of memory",
    "connection refused",
    "test failure in UserServiceTest",
    "compilation error: syntax error"
]

now = datetime.now(timezone.utc)

for repo in repositories:
    # Create builds over last 30 days
    for day_offset in range(30):
        build_date = now - timedelta(days=day_offset)
        
        # Create 2-5 builds per day
        num_builds = random.randint(2, 5)
        
        for build_num in range(num_builds):
            build_time = build_date + timedelta(hours=random.randint(0, 23), minutes=random.randint(0, 59))
            
            # Some builds fail
            state = random.choice(["SUCCESSFUL", "SUCCESSFUL", "SUCCESSFUL", "FAILED"])
            
            # Duration varies - recent builds are slower (regression simulation)
            if day_offset < 14:  # Recent builds
                base_duration = random.uniform(300, 600)  # Slower
            else:  # Older builds
                base_duration = random.uniform(200, 400)  # Faster
            
            duration = base_duration + random.uniform(-50, 50)
            completed_time = build_time + timedelta(seconds=duration)
            
            build = Build(
                repository_id=repo.id,
                build_number=build_num + 1,
                pipeline_uuid=f"pipeline-{repo.id}-{day_offset}-{build_num}",
                commit_hash=f"abc{random.randint(1000, 9999)}def",
                branch="main",
                state=state,
                duration_seconds=duration,
                started_on=build_time,
                completed_on=completed_time if state != "IN_PROGRESS" else None,
                trigger_name="manual"
            )
            db.add(build)
            db.flush()
            
            # Add steps
            step_duration_sum = 0
            for i, step_name in enumerate(step_names):
                step_duration = duration / len(step_names) + random.uniform(-10, 10)
                step_duration_sum += step_duration
                
                step_started = build_time + timedelta(seconds=step_duration_sum - step_duration)
                step_completed = step_started + timedelta(seconds=step_duration)
                
                step_state = state if i < len(step_names) - 1 else state
                
                step = BuildStep(
                    build_id=build.id,
                    step_name=step_name,
                    step_type="script",
                    duration_seconds=step_duration,
                    state=step_state,
                    started_on=step_started,
                    completed_on=step_completed if step_state != "IN_PROGRESS" else None,
                    max_time_seconds=step_duration * 3,  # Waste: 3x actual time
                    memory_limit_mb=4096,
                    peak_memory_mb=random.randint(512, 1024)  # Waste: 4x peak
                )
                db.add(step)
                
                # Add failure if step failed
                if step_state == "FAILED":
                    error_msg = random.choice(error_patterns)
                    pattern_matcher = PatternMatcher(db)
                    pattern = pattern_matcher.normalize_error_message(error_msg)
                    
                    failure = BuildFailure(
                        build_id=build.id,
                        step_id=step.id,
                        error_message=error_msg,
                        error_pattern=pattern,
                        failure_type=pattern_matcher._classify_failure(error_msg),
                        occurred_at=step_completed or build_time
                    )
                    db.add(failure)
    
    # Create PRs - use unique pr_id per repository
    for pr_num in range(20):
        created = now - timedelta(days=random.randint(0, 30))
        merged = created + timedelta(hours=random.randint(2, 48))
        
        # Check if PR already exists for this repo
        existing = db.query(PullRequest).filter(
            PullRequest.repository_id == repo.id,
            PullRequest.pr_id == pr_num + 1
        ).first()
        
        if not existing:
            pr = PullRequest(
                repository_id=repo.id,
                pr_id=pr_num + 1,
                title=f"Feature PR {pr_num + 1}",
                state="MERGED",
                created_at=created,
                merged_at=merged,
                author=f"developer{random.randint(1, 5)}"
            )
            db.add(pr)
    
    # Create deployments
    environments = ["staging", "production"]
    for env in environments:
        for dep_num in range(5):
            deployed = now - timedelta(days=random.randint(0, 30))
            dep = Deployment(
                repository_id=repo.id,
                environment=env,
                docker_image=f"{repo.slug}:v1.{dep_num}.0",
                deployed_at=deployed,
                commit_hash=f"abc{random.randint(1000, 9999)}def"
            )
            db.add(dep)

db.commit()
print("Mock data seeded successfully!")
print(f"Created {len(repositories)} repositories")
print("Run: curl -X POST http://localhost:8000/api/diagnostics/generate")

