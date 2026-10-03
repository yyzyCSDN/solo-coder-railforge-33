from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    id: str
    max_height_m: float
    max_width_m: float
    max_gross_t: float
    max_axle_t: float


@dataclass(frozen=True)
class TrainProfile:
    height_m: float
    width_m: float
    gross_t: float
    max_axle_t: float


@dataclass(frozen=True)
class SegmentViolation:
    segment_id: str
    limit: str
    required: float
    actual: float

    def as_dict(self) -> dict[str, object]:
        return {
            "segment_id": self.segment_id,
            "limit": self.limit,
            "required_max": self.required,
            "actual": self.actual,
        }


@dataclass(frozen=True)
class ClearanceResult:
    allowed: bool
    violations: tuple[SegmentViolation, ...]

    def as_dict(self) -> dict[str, object]:
        return {"allowed": self.allowed,
                "violations": [v.as_dict() for v in self.violations]}


_CHECKS = (
    ("height_m", "max_height_m"),
    ("width_m", "max_width_m"),
    ("gross_t", "max_gross_t"),
    ("axle_t", "max_axle_t"),
)


def evaluate_clearance(profile: TrainProfile, segments: list[Segment]) -> ClearanceResult:
    """Check every segment independently against height, width, gross and axle limits.

    A single permissive segment must never clear the whole route: every failed
    segment is collected and reported, not just the first one.
    """
    actuals = {
        "height_m": profile.height_m,
        "width_m": profile.width_m,
        "gross_t": profile.gross_t,
        "axle_t": profile.max_axle_t,
    }
    violations: list[SegmentViolation] = []
    for segment in segments:
        limits = {
            "height_m": segment.max_height_m,
            "width_m": segment.max_width_m,
            "gross_t": segment.max_gross_t,
            "axle_t": segment.max_axle_t,
        }
        for limit_name, _ in _CHECKS:
            actual = actuals[limit_name]
            allowed_max = limits[limit_name]
            if actual > allowed_max:
                violations.append(SegmentViolation(
                    segment.id, limit_name, allowed_max, actual))
    return ClearanceResult(not violations, tuple(violations))


def route_ok(profile: TrainProfile, segments: list[Segment]) -> bool:
    """True only when every segment of the route satisfies every limit."""
    return evaluate_clearance(profile, segments).allowed
