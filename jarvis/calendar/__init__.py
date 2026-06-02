"""Calendar (Phase 2): read-only Google Calendar behind the trust boundary.

This package is the ONLY place the three official Google libraries may be imported (it is
boundary-guarded). OAuth secrets live in ./data/ (git-ignored). Phase 2 is read-only; confirmed
event creation is a separate, deferrable slice (3b).
"""
