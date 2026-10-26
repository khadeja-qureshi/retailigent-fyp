import os

# Tests must never start the real background scheduler (it would poll a
# database). Tests that exercise the lifespan monkeypatch build_scheduler.
os.environ.setdefault("SCHEDULER_ENABLED", "false")
