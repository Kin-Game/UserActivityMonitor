from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Session:
    start: datetime
    end: Optional[datetime]
    app: str
    title: str
    category: Optional[str]
    idle: bool


@dataclass
class LimitRule:
    category: str
    daily_limit_minutes: int


@dataclass
class Recommendation:
    timestamp: datetime
    category: str
    message: str
