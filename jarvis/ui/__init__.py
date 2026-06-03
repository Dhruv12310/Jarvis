"""UI (Phase 3): a thin desktop front-end (Flet) over JarvisService.

`feed.py` and `controller.py` are pure (no Flet), so the feed model + dispatch are unit-tested
without launching a window; `app.py` is the only Flet importer (the toolkit stays swappable).
"""
