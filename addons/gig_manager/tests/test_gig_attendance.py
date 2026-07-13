"""gig.attendance: unique (partner, event), default status, the
related/stored project_id, cascades from both sides.
"""
import psycopg2

from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestGigAttendance(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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
        # one RSVP per (musician, event), DB-enforced
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
        # rows get pre-created before anyone confirmed anything
        attendance = self.env['gig.attendance'].create({
            'partner_id': self.partner.id,
            'event_id': self.event.id,
        })
        self.assertEqual(attendance.status, 'maybe')

    def test_project_id_computed_from_event_at_creation(self):
        # related + store: filled from the event automatically, no need
        # (and no way, it's readonly) to pass it
        attendance = self.env['gig.attendance'].create({
            'partner_id': self.partner.id,
            'event_id': self.event.id,
        })
        self.assertEqual(attendance.project_id, self.project)

    def test_project_id_updates_when_event_changes(self):
        """Related fields derive their dependencies from the dotted
        path - no @api.depends to forget, unlike the display_name
        computes that each needed a fix. Moving the row to an event of
        another project must move project_id with it.
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
        partner = self.env['res.partner'].create({'name': 'Temporary Attendee'})
        attendance = self.env['gig.attendance'].create({
            'partner_id': partner.id,
            'event_id': self.event.id,
        })
        partner.unlink()
        self.assertFalse(attendance.exists())

    def test_deleting_event_cascades(self):
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
