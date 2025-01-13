from dataclasses import dataclass


@dataclass
class _caseinsensitive:
    _s: str

    def __hash__(self) -> int:
        return hash(self._s.upper())


iexact = _caseinsensitive

__all__ = ["iexact"]
