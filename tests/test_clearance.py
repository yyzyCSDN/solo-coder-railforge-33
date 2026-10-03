import unittest
from datetime import datetime, timezone

from railforge.routing.clearance import (
    Segment, TrainProfile, evaluate_route, route_ok,
    HEIGHT, WIDTH, GROSS, AXLE,
)
from railforge.workflows.control import RailForgeWorkflowControl
from railforge.workflows.features import RailForgeFeatureService

U = timezone.utc
AT = datetime(2026, 10, 2, tzinfo=U)
PROFILE = TrainProfile(height_m=5.0, width_m=3.0, gross_t=80.0, max_axle_t=22.0)
FITS = Segment("S1", max_height_m=5.5, max_width_m=3.2, max_gross_t=100, max_axle_t=25)
TIGHT = Segment("S2", max_height_m=4.5, max_width_m=2.8, max_gross_t=90, max_axle_t=25)


class ClearanceTests(unittest.TestCase):
    def test_one_fitting_segment_must_not_release_whole_route(self):
        # Regression: any(...) over segments ignored the lower-clearance one.
        self.assertFalse(route_ok(PROFILE, [FITS, TIGHT]))
        self.assertFalse(route_ok(PROFILE, [TIGHT, FITS]))
        self.assertTrue(route_ok(PROFILE, [FITS]))

    def test_every_dimension_checked_per_segment(self):
        cases = {
            "height": Segment("h", 4.9, 9, 999, 99),
            "width": Segment("w", 9, 2.9, 999, 99),
            "gross": Segment("g", 9, 9, 79, 99),
            "axle": Segment("a", 9, 9, 999, 21),
        }
        expected = {
            "height": HEIGHT, "width": WIDTH, "gross": GROSS, "axle": AXLE,
        }
        for name, seg in cases.items():
            report = evaluate_route(PROFILE, [seg])
            self.assertFalse(report.clear)
            self.assertEqual(report.failed_segments[0].violations, (expected[name],))

    def test_multiple_dimensions_reported_together(self):
        report = evaluate_route(PROFILE, [FITS, TIGHT])
        self.assertFalse(report.clear)
        failed = report.failed_segments
        self.assertEqual([c.segment_id for c in failed], ["S2"])
        self.assertEqual(set(failed[0].violations), {HEIGHT, WIDTH})

    def test_boundary_equality_passes(self):
        self.assertTrue(route_ok(PROFILE, [Segment("eq", 5.0, 3.0, 80.0, 22.0)]))


class RejectionEventTests(unittest.TestCase):
    def test_rejection_event_is_persisted_and_hash_chained(self):
        ctl = RailForgeWorkflowControl()
        receipt = ctl.check_clearance("op-1", PROFILE, [FITS, TIGHT], "TRAIN-7", AT)
        self.assertFalse(bool(receipt.result))
        rejected = [e for e in ctl.stream.snapshot()
                    if e.topic == "routing.clearance.rejected"]
        self.assertEqual(len(rejected), 1)
        event = rejected[0]
        self.assertEqual(event.payload["status"], "rejected")
        self.assertEqual(event.payload["failed_segments"],
                         [{"segment_id": "S2", "violations": ["height", "width"]}])
        self.assertTrue(ctl.stream.verify_chain())
        self.assertTrue(ctl.trail.verify())

    def test_tampering_with_rejection_is_detectable(self):
        ctl = RailForgeWorkflowControl()
        ctl.check_clearance("op-1", PROFILE, [FITS, TIGHT], "TRAIN-7", AT)
        event = next(e for e in ctl.stream.snapshot()
                     if e.topic == "routing.clearance.rejected")
        event.payload["status"] = "committed"
        self.assertFalse(ctl.stream.verify_chain())

    def test_approved_route_emits_no_rejection(self):
        ctl = RailForgeWorkflowControl()
        ctl.check_clearance("op-2", PROFILE, [FITS], "TRAIN-8", AT)
        topics = {e.topic for e in ctl.stream.snapshot()}
        self.assertEqual(topics, {"routing.clearance.checked"})
        self.assertTrue(ctl.stream.verify_chain())

    def test_rejection_idempotent_on_replay(self):
        ctl = RailForgeWorkflowControl()
        ctl.check_clearance("op-1", PROFILE, [FITS, TIGHT], "TRAIN-7", AT)
        ctl.check_clearance("op-1", PROFILE, [FITS, TIGHT], "TRAIN-7", AT)
        self.assertEqual(
            sum(1 for e in ctl.stream.snapshot()
                if e.topic == "routing.clearance.rejected"),
            1,
        )

    def test_feature_service_raises_but_rejection_is_already_committed(self):
        ctl = RailForgeWorkflowControl()
        svc = RailForgeFeatureService(ctl)
        with self.assertRaises(ValueError) as ctx:
            svc.check_route_clearance("op-3", PROFILE, [FITS, TIGHT], [],
                                      lambda w: True, AT)
        self.assertIn("S2", str(ctx.exception))
        topics = {e.topic for e in ctl.stream.snapshot()}
        self.assertIn("routing.clearance.rejected", topics)
        self.assertTrue(ctl.stream.verify_chain())
        self.assertTrue(ctl.trail.verify())


if __name__ == "__main__":
    unittest.main()
