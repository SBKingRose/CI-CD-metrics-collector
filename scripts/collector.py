import sys
from pathlib import Path
import time

# Add parent directory to path so we can import app
sys.path.insert(0, str(Path(__file__).parent.parent))

from apscheduler.schedulers.blocking import BlockingScheduler
from app.collector import DataCollector
from app.diagnostics import DiagnosticEngine
from app.database import SessionLocal
from app.config import settings

def collect_and_analyze():
    """Collect data and generate diagnostics"""
    db = SessionLocal()
    try:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting data collection...")
        collector = DataCollector(db)
        collector.collect_all()
        
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Generating diagnostics...")
        engine = DiagnosticEngine(db)
        diagnostics = engine.generate_diagnostics()
        engine.save_diagnostics(diagnostics)
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Generated {len(diagnostics)} diagnostics")
    except Exception as e:
        print(f"Error in collection cycle: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    print("Starting Release Intelligence Platform data collector...")
    print(f"Collection interval: {settings.collection_interval_minutes} minutes")
    
    # Run immediately
    collect_and_analyze()
    
    # Schedule periodic collection
    scheduler = BlockingScheduler()
    scheduler.add_job(
        collect_and_analyze,
        'interval',
        minutes=settings.collection_interval_minutes
    )
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

