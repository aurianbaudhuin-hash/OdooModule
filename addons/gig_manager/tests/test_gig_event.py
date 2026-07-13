"""gig.event: name-vs-type constraint, time bounds, the onchange (via
Form), display_name, cascade from project.
"""
from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests import Form
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGigEvent(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # section_group_id is required on projects; which one doesn't
        # matter for event tests
        cls.section_group = cls.env['gig.section.group'].create(
            {'name': 'Test Fixture Event Test Orchestra'})
        cls.project = cls.env['gig.project'].create({
            'name': 'Autumn Tour',
            'section_group_id': cls.section_group.id,
        })

    def test_rehearsal_with_name_raises(self):
        # the view hides the name field for rehearsals, but that's
        # cosmetic - this checks the model-level rule that actually
        # holds for imports/code
        with self.assertRaises(ValidationError):
            self.env['gig.event'].create({
                'project_id': self.project.id,
                'event_type': 'rehearsal',
                'name': 'This should not be allowed',
                'event_date': '2026-08-01',
                'start_time': 10.0,
                'end_time': 12.0,
            })

    def test_concert_with_name_allowed(self):
        event = self.env['gig.event'].create({
            'project_id': self.project.id,
            'event_type': 'concert',
            'name': 'Opening Night',
            'event_date': '2026-08-01',
            'start_time': 19.0,
            'end_time': 21.0,
        })
        self.assertTrue(event.id)

    def test_time_bounds_reject_negative_and_overflow(self):
        # a Float will hold anything, the constraint is the only thing
        # keeping times inside 0-24
        with self.assertRaises(ValidationError):
            self.env['gig.event'].create({
                'project_id': self.project.id,
                'event_type': 'concert',
                'event_date': '2026-08-01',
                'start_time': -1.0,
                'end_time': 12.0,
            })
        with self.assertRaises(ValidationError):
            self.env['gig.event'].create({
                'project_id': self.project.id,
                'event_type': 'concert',
                'event_date': '2026-08-01',
                'start_time': 10.0,
                'end_time': 24.0,
            })

    def test_end_time_before_start_time_raises(self):
        with self.assertRaises(ValidationError):
            self.env['gig.event'].create({
                'project_id': self.project.id,
                'event_type': 'concert',
                'event_date': '2026-08-01',
                'start_time': 12.0,
                'end_time': 10.0,
            })

    def test_valid_times_allowed(self):
        event = self.env['gig.event'].create({
            'project_id': self.project.id,
            'event_type': 'concert',
            'event_date': '2026-08-01',
            'start_time': 10.0,
            'end_time': 12.0,
        })
        self.assertTrue(event.id)

    def test_onchange_clears_name_when_switching_to_rehearsal(self):
        """Through Form: it drives the same onchange dispatch as the
        web client, calling the method directly would prove nothing
        about the UI. Also shows a dynamically-invisible field stays
        reachable in Form state.
        """
        form = Form(self.env['gig.event'])
        form.project_id = self.project
        form.event_date = date(2026, 8, 1)
        form.start_time = 10.0
        form.end_time = 12.0
        form.name = 'Draft Concert Name'
        self.assertEqual(form.name, 'Draft Concert Name')
        form.event_type = 'rehearsal'
        self.assertFalse(form.name)

    def test_display_name_for_rehearsal(self):
        event = self.env['gig.event'].create({
            'project_id': self.project.id,
            'event_type': 'rehearsal',
            'event_date': '2026-08-01',
            'start_time': 10.0,
            'end_time': 12.0,
        })
        self.assertEqual(event.display_name, f"Rehearsal — {event.event_date}")

    def test_display_name_for_named_concert(self):
        event = self.env['gig.event'].create({
            'project_id': self.project.id,
            'event_type': 'concert',
            'name': 'Opening Night',
            'event_date': '2026-08-01',
            'start_time': 19.0,
            'end_time': 21.0,
        })
        self.assertEqual(event.display_name, 'Opening Night')

    def test_display_name_for_unnamed_concert(self):
        # (the "no date" branch of the compute isn't tested - it's
        # unreachable for a persisted record since event_date is
        # required)
        event = self.env['gig.event'].create({
            'project_id': self.project.id,
            'event_type': 'concert',
            'event_date': '2026-08-01',
            'start_time': 19.0,
            'end_time': 21.0,
        })
        self.assertEqual(event.display_name, f"Concert — {event.event_date}")

    def test_deleting_project_cascades_to_events(self):
        project = self.env['gig.project'].create({
            'name': 'Short Lived Tour',
            'section_group_id': self.section_group.id,
        })
        event = self.env['gig.event'].create({
            'project_id': project.id,
            'event_type': 'concert',
            'event_date': '2026-08-01',
            'start_time': 10.0,
            'end_time': 12.0,
        })
        project.unlink()
        self.assertFalse(event.exists())
