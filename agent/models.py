from dataclasses import dataclass, asdict


@dataclass
class ThreatAnalysis:
    domain: str
    is_threat: bool
    confidence: float  # 0.0 to 1.0
    reason: str
    risk_level: str
    timestamp: str

    def to_dict(self) -> dict:
        """Convert to dictionary for CSV/JSON serialization"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'ThreatAnalysis':
        """Create from dictionary"""
        return cls(**data)


@dataclass
class AnalysisMetadata:
    brand: str
    keyword: str
    total_domains: int
    threat_count: int
    filtered_count: int
    false_positive_reduction: str
    timestamp: str
    batch_size: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BrandAnalysisResult:
    metadata: AnalysisMetadata
    threats: list[ThreatAnalysis]
    filtered: list[ThreatAnalysis]

    def to_dict(self) -> dict:
        return {
            'metadata': self.metadata.to_dict(),
            'relevant_domains': [threat.to_dict() for threat in self.threats],
            'filtered_domains': [filtered.to_dict() for filtered in self.filtered]
        }
