from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
from datetime import datetime, timezone


class Repository(Base):
    __tablename__ = "repositories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    slug = Column(String)
    workspace = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    builds = relationship("Build", back_populates="repository")
    deployments = relationship("Deployment", back_populates="repository")
    pull_requests = relationship("PullRequest", back_populates="repository")


class Build(Base):
    __tablename__ = "builds"
    
    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"))
    build_number = Column(Integer, index=True)
    pipeline_uuid = Column(String, index=True)
    commit_hash = Column(String, index=True)
    branch = Column(String, index=True)
    state = Column(String)  # SUCCESSFUL, FAILED, IN_PROGRESS, STOPPED
    duration_seconds = Column(Float)
    started_on = Column(DateTime, index=True)
    completed_on = Column(DateTime)
    trigger_name = Column(String)
    
    repository = relationship("Repository", back_populates="builds")
    steps = relationship("BuildStep", back_populates="build")


class BuildStep(Base):
    __tablename__ = "build_steps"
    
    id = Column(Integer, primary_key=True, index=True)
    build_id = Column(Integer, ForeignKey("builds.id"))
    step_uuid = Column(String, nullable=True, index=True)  # Bitbucket step UUID (if available)
    step_name = Column(String, index=True)
    step_type = Column(String)  # script, docker, manual
    duration_seconds = Column(Float)
    state = Column(String)
    started_on = Column(DateTime)
    completed_on = Column(DateTime)
    max_time_seconds = Column(Float, nullable=True)
    memory_limit_mb = Column(Integer, nullable=True)
    peak_memory_mb = Column(Integer, nullable=True)
    size_factor = Column(Integer, nullable=True)  # 1,2,4... best-effort
    log_excerpt = Column(Text, nullable=True)  # best-effort captured log excerpt (esp. failures)
    
    build = relationship("Build", back_populates="steps")


class PullRequest(Base):
    __tablename__ = "pull_requests"
    __table_args__ = (
        UniqueConstraint('repository_id', 'pr_id', name='uq_repo_pr'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), index=True)
    pr_id = Column(Integer, index=True)  # Unique per repository, not globally
    title = Column(String)
    state = Column(String)  # OPEN, MERGED, DECLINED
    created_at = Column(DateTime, index=True)
    merged_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    author = Column(String)
    
    repository = relationship("Repository", back_populates="pull_requests")


class Deployment(Base):
    __tablename__ = "deployments"
    
    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"))
    environment = Column(String, index=True)  # staging, production, etc.
    docker_image = Column(String, index=True)
    deployed_at = Column(DateTime, index=True)
    build_id = Column(Integer, ForeignKey("builds.id"), nullable=True)
    commit_hash = Column(String)
    
    repository = relationship("Repository", back_populates="deployments")


class BuildFailure(Base):
    __tablename__ = "build_failures"
    
    id = Column(Integer, primary_key=True, index=True)
    build_id = Column(Integer, ForeignKey("builds.id"))
    step_id = Column(Integer, ForeignKey("build_steps.id"), nullable=True)
    error_message = Column(Text)
    error_pattern = Column(String, index=True)  # Normalized pattern for matching
    failure_type = Column(String)  # timeout, compilation_error, test_failure, etc.
    occurred_at = Column(DateTime, index=True)
    
    build = relationship("Build")


class Diagnostic(Base):
    __tablename__ = "diagnostics"
    
    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=True)
    diagnostic_type = Column(String, index=True)  # regression, resource_waste, pattern_match
    severity = Column(String)  # high, medium, low
    title = Column(String)
    message = Column(Text)
    diagnostic_metadata = Column(JSON)  # Store additional context (renamed from metadata to avoid SQLAlchemy conflict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    acknowledged = Column(Boolean, default=False)
    
    repository = relationship("Repository")

