import typing
import re
import sqlalchemy as sa
from sqlalchemy.orm import InstrumentedAttribute


def text_to_tsvector(
    text: typing.Union[str, InstrumentedAttribute[str]], language: str = "english"
):
    """Convert text to a tsvector for full-text search."""
    return sa.func.to_tsvector(language, text)


def text_to_tsquery(
    text: typing.Union[str, InstrumentedAttribute[str]], language: str = "english"
):
    """Convert text to a tsquery for full-text search."""
    return sa.func.plainto_tsquery(language, text)


def query_to_regex_pattern(query: str) -> str:
    """Convert search query to a flexible regex pattern.
    Handles spaces, hyphens, and other word separators flexibly."""
    cleaned = query.strip().lower()
    escaped = re.escape(cleaned)
    words = escaped.split(r"\ ")
    pattern = r".*".join(words)
    return f".*{pattern}.*"
