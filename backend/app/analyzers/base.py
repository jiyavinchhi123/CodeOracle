from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParsedFile:
    path: str
    language: str
    line_count: int
    size_bytes: int
    content: str
    classes: list = field(default_factory=list)
    functions: list = field(default_factory=list)
    imports: list = field(default_factory=list)
    parse_error: Optional[str] = None


class BaseAnalyzer(ABC):
    @abstractmethod
    def can_analyze(self, path: str) -> bool:
        ...

    @abstractmethod
    def analyze_file(self, path: str, content: str) -> ParsedFile:
        ...
