"""Tests for gig.event: the rehearsal-cannot-have-a-name constraint, the
start/end time bounds constraint, the _onchange_event_type name-clearing
behaviour (exercised via Form, not by calling the method directly),
display_name for both event types, and the cascade-delete from
gig.project.
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
        cls.project = cls.env['gig.project'].create({'name': 'Autumn Tour'})

    def test_rehearsal_with_name_raises(self):
        """_check_name_by_type: a rehearsal must never carry a name - the
        view already hides the name field once event_type is 'rehearsal'
        (invisible="event_type == 'rehearsal'"), but per this codebase's
        convention that's UX only; the actual guarantee has to live here
        at the model level so it holds even for writes that bypass the
        form (imports, other code, etc.)."""
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
        """A concert, unlike a rehearsal, is allowed (though not required)
        to carry a name."""
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
        """_check_times requires 0 <= value < 24 for both start_time and
        end_time - a Float time field can technically hold any number,
        so this constraint is what actually keeps it inside a single day."""
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
        """An event that ends before (or exactly when) it starts is
        never valid, regardless of whether both individual times are
        within the 0-24 range."""
        with self.assertRaises(ValidationError):
            self.env['gig.event'].create({
                'project_id': self.project.id,
                'event_type': 'concert',
                'event_date': '2026-08-01',
                'start_time': 12.0,
                'end_time': 10.0,
            })

    def test_valid_times_allowed(self):
        """A sane start-before-end range within a single day must be accepted."""
        event = self.env['gig.event'].create({
            'project_id': self.project.id,
            'event_type': 'concert',
            'event_date': '2026-08-01',
            'start_time': 10.0,
            'end_time': 12.0,
        })
        self.assertTrue(event.id)

    def test_onchange_clears_name_when_switching_to_rehearsal(self):
        """_onchange_event_type must be exercised through Form, not by
        calling the decorated method directly on a browsed record: Form
        drives the same onchange dispatch graph the web client uses,
        whereas calling the method directly would just run that one
        function in isolation and wouldn't prove the UI actually behaves
        this way. This also implicitly verifies the field stays reachable
        through Form despite its invisible="event_type == 'rehearsal'"
        condition in the view - dynamic invisible doesn't remove a field
        from Form's tracked state, only from what's rendered.
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
        """A rehearsal always renders as "Rehearsal — <date>", regardless
        of any other field, since rehearsals can never have a name."""
        event = self.env['gig.event'].create({
            'project_id': self.project.id,
            'event_type': 'rehearsal',
            'event_date': '2026-08-01',
            'start_time': 10.0,
            'end_time': 12.0,
        })
        self.assertEqual(event.display_name, f"Rehearsal — {event.event_date}")

    def test_display_name_for_named_concert(self):
        """A concert with a name uses that name directly."""
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
        """A concert without a name falls back to "Concert — <date>".

        Note: the third branch inside _compute_display_name (event_date
        missing entirely, falling back to the "no date" placeholder) is
        not exercised here - event_date is required=True, so it's
        unreachable through a normal create() call; there's no
        persisted record that could ever hit that branch.
        """
        event = self.env['gig.event'].create({
            'project_id': self.project.id,
            'event_type': 'concert',
            'event_date': '2026-08-01',
            'start_time': 19.0,
            'end_time': 21.0,
        })
        self.assertEqual(event.display_name, f"Concert — {event.event_date}")

    def test_deleting_project_cascades_to_events(self):
        """project_id uses ondelete='cascade' - an event has no meaning
        without its parent project, so deleting the project must remove
        its events rather than leaving them orphaned or blocking the
        project's deletion."""
        project = self.env['gig.project'].create({'name': 'Short Lived Tour'})
        event = self.env['gig.event'].create({
            'project_id': project.id,
            'event_type': 'concert',
            'event_date': '2026-08-01',
            'start_time': 10.0,
            'end_time': 12.0,
        })
        project.unlink()
        self.assertFalse(event.exists())
