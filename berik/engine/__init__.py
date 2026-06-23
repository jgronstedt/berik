"""Berik enrichment engine — pure Python, no UI. Import and call analyze()/commit()."""
from .pipeline import analyze, commit          # noqa: F401
from .model import Analysis, CommitResult       # noqa: F401
