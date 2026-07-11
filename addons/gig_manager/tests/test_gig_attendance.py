"""Tests for gig.attendance: the unique(partner_id, event_id) constraint,
the default 'maybe' status, the related/store project_id field (both at
creation and after moving the row to a different event), and cascade
deletes from either side (partner_id, event_id).
"""
import psycopg2

from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestGigAttendance(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # gig.project.section_group_id is required; which layout the
        # project points at is irrelevant to every attendance test here.
        cls.section_group = cls.env['gig.section.group'].create(
            {'name': 'Test Fixture Attendance Test Orchestra'})
        cls.project = cls.env['gig.project'].create({
            'name': 'Attendance Test Tour',
            'section_group_id': cls.section_group.id,
        })
        cls.event = cls.env['gig.event'].create({
            'project_id': cls.project.id,
            'event_type': 'concert',
            'event_date': '2026-09-01',
            'start_time': 19.0,
            'end_time': 21.0,
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Attendance Test Musician'})

    def test_duplicate_partner_event_raises(self):
        """_sql_constraints unique(partner_id, event_id): a musician can
        only have one RSVP status per event - a second row for the same
        pair would just be an ambiguous duplicate, so this must be
        enforced at the DB level."""
        self.env['gig.attendance'].create({
            'partner_id': self.partner.id,
            'event_id': self.event.id,
        })
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self.env['gig.attendance'].create({
                'partner_id': self.partner.id,
                'event_id': self.event.id,
            })
            self.env.flush_all()

    def test_default_status_is_maybe(self):
        """An attendance row created without an explicit status should
        default to 'maybe' - matching the documented workflow where
        rows are pre-created for every participant ahead of the event,
        before anyone has actually confirmed whether they're coming."""
        attendance = self.env['gig.attendance'].create({
            'partner_id': self.partner.id,
            'event_id': self.event.id,
        })
        self.assertEqual(attendance.status, 'maybe')

    def test_project_id_computed_from_event_at_creation(self):
        """project_id is related='event_id.project_id', store=True - it
        should be populated automatically from the event's project the
        moment event_id is set, with no need to pass project_id explicitly
        (indeed, passing it would be pointless: it's readonly=True)."""
        attendance = self.env['gig.attendance'].create({
            'partner_id': self.partner.id,
            'event_id': self.event.id,
        })
        self.assertEqual(attendance.project_id, self.project)

    def test_project_id_updates_when_event_changes(self):
        """Unlike the plain @api.depends computes elsewhere in this
        module (gig.composer/gig.event's display_name, gig.project's
        attendance_count - all of which needed an explicit fix, see
        their own tests), a related field's dependency graph is derived
        automatically from its dotted path (event_id.project_id) - Odoo
        doesn't need a manually declared @api.depends for related fields
        to stay in sync. Moving this attendance row to an event on a
        different project must update project_id accordingly, with no
        extra wiring required.
        """
        other_project = self.env['gig.project'].create({
            'name': 'Other Tour',
            'section_group_id': self.section_group.id,
        })
        other_event = self.env['gig.event'].create({
            'project_id': other_project.id,
            'event_type': 'concert',
            'event_date': '2026-10-01',
            'start_time': 20.0,
            'end_time': 22.0,
        })
        attendance = self.env['gig.attendance'].create({
            'partner_id': self.partner.id,
            'event_id': self.event.id,
        })
        self.assertEqual(attendance.project_id, self.project)
        attendance.event_id = other_event
        self.assertEqual(attendance.project_id, other_project)

    def test_deleting_partner_cascades(self):
        """partner_id uses ondelete='cascade' - an attendance row is
        meaningless without the musician it refers to."""
        partner = self.env['res.partner'].create({'name': 'Temporary Attendee'})
        attendance = self.env['gig.attendance'].create({
            'partner_id': partner.id,
            'event_id': self.event.id,
        })
        partner.unlink()
        self.assertFalse(attendance.exists())

    def test_deleting_event_cascades(self):
        """event_id uses ondelete='cascade' - an attendance row is
        meaningless without the event it refers to."""
        event = self.env['gig.event'].create({
            'project_id': self.project.id,
            'event_type': 'concert',
            'event_date': '2026-11-01',
            'start_time': 19.0,
            'end_time': 21.0,
        })
        attendance = self.env['gig.attendance'].create({
            'partner_id': self.partner.id,
            'event_id': event.id,
        })
        event.unlink()
        self.assertFalse(attendance.exists())
