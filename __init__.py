"""Contains helper and utility modules that aid faster development of api application(s)."""
from pathlib import Path
import os

from .dependencies import deps_required

__author__ = "Daniel T. Afolayan (ti-oluwa@github)"

RESOURCES_PATH = Path(__file__).resolve().parent / "resources"

deps_required(
    {
        "typing_extensions": "typing-extensions",
    }
)
