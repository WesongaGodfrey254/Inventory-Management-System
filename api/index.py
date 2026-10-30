"""Vercel serverless entry point.

Vercel's Python runtime looks for a module-level ``app`` (WSGI callable) in
``api/index.py``. The project root is added to ``sys.path`` so the application
package can be imported exactly as it is locally.
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app  # noqa: E402

app = create_app()
