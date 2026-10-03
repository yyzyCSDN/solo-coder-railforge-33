from __future__ import annotations

from dataclasses import dataclass

# Dimensions checked for every segment, in audit order.
HEIGHT = "height"
WIDTH = "width"
GROSS = "gross"
AXLE = "axle"
DIMENSIONS: tuple[str, ...] = (HEIGHT, WIDTH, GROSS, AXLE)


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
class SegmentCheck:
    """Per-segment result. ``violations`` lists every dimension that fails."""
    segment_id: str
    allowed: bool
    violations: tuple[str, ...]
    height_m: float
    max_height_m: float
    width_m: float
    max_width_m: float
    gross_t: float
    max_gross_t: float
    axle_t: float
    max_axle_t: float


@dataclass(frozen=True)
class RouteClearanceReport:
    clear: bool
    segments: tuple[SegmentCheck, ...]

    @property
    def failed_segments(self) -> tuple[SegmentCheck, ...]:
        return tuple(s for s in self.segments if not s.allowed)

    def __bool__(self) -> bool:
        return self.clear


def check_segment(profile: TrainProfile, segment: Segment) -> SegmentCheck:
    """Check height, width, gross weight and axle load against one segment."""
    violations: list[str] = []
    if profile.height_m > segment.max_height_m:
        violations.append(HEIGHT)
    if profile.width_m > segment.max_width_m:
        violations.append(WIDTH)
    if profile.gross_t > segment.max_gross_t:
        violations.append(GROSS)
    if profile.max_axle_t > segment.max_axle_t:
        violations.append(AXLE)
    return SegmentCheck(
        segment_id=segment.id,
        allowed=not violations,
        violations=tuple(violations),
        height_m=profile.height_m,
        max_height_m=segment.max_height_m,
        width_m=profile.width_m,
        max_width_m=segment.max_width_m,
        gross_t=profile.gross_t,
        max_gross_t=segment.max_gross_t,
        axle_t=profile.max_axle_t,
        max_axle_t=segment.max_axle_t,
    )


def check_segments(profile: TrainProfile, segments: list[Segment]) -> tuple[SegmentCheck, ...]:
    return tuple(check_segment(profile, s) for s in segments)


def evaluate_route(profile: TrainProfile, segments: list[Segment]) -> RouteClearanceReport:
    checks = check_segments(profile, segments)
    # Every segment must satisfy every dimension; one tight segment denies the route.
    return RouteClearanceReport(clear=all(c.allowed for c in checks), segments=checks)


def route_ok(profile: TrainProfile, segments: list[Segment]) -> bool:
    return evaluate_route(profile, segments).clear
