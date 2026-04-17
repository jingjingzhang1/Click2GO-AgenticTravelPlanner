"""
Test configuration — use SQLite for fast, isolated testing.
This must be imported before any backend modules.
"""
import os

# Override DATABASE_URL to use SQLite for tests
os.environ["DATABASE_URL"] = "sqlite:///./test_click2go.db"
