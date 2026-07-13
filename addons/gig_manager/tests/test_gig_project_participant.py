"""gig.project.participant: unique (project, partner), the
section-in-group rule (both sides), the attendance auto-creation on
registration (incl. re-registration), cascades and restricts.
"""
import psycopg2

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestGigProjectParticipant(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.violin = cls.env['gig.instrument'].create(
            {'name': 'Test Fixture Registration Violin'})
        # one section inside the project's group, one outside - the
        # constraint tests need both
        cls.section = cls.env['gig.section'].create({
            'name': 'Test Fixture Registration Strings',
            'instrument_line_ids': [
                Command.create({'instrument_id': cls.violin.id, 'quantity': 8}),
            ],
        })
        cls.outside_section = cls.env['gig.section'].create({
            'name': 'Test Fixture Outside Section',
            'instrument_line_ids': [
                Command.create({'instrument_id': cls.violin.id, 'quantity': 2}),
            ],
        })
        cls.group = cls.env['gig.section.group'].create(
            {'name': 'Test Fixture Registration Orchestra'})
        cls.env['gig.section.group.line'].create({
            'group_id': cls.group.id,
            'section_id': cls.section.id,
        })
        cls.project = cls.env['gig.project'].create({
            'name': 'Registration Test Tour',
            'section_group_id': cls.group.id,
        })
        cls.partner = cls.env['res.partner'].create(
            {'name': 'Registration Test Musician'})

    def _create_event(self, event_date):
        return self.env['gig.event'].create({
            'project_id': self.project.id,
            'event_type': 'concert',
            'event_date': event_date,
            'start_time': 19.0,
            'end_time': 21.0,
        })

    def _register(self, partner, section=None):
        return self.env['gig.project.participant'].create({
            'project_id': self.project.id,
            'partner_id': partner.id,
            'section_id': (section or self.section).id,
        })

    def test_duplicate_registration_raises(self):
        # a musician plays in exactly one section per project
        self._register(self.partner)
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self._register(self.partner)
            self.env.flush_all()

    def test_section_outside_project_group_raises(self):
        # the view's domain filters the dropdown, this checks the
        # actual model rule behind it
        with self.assertRaises(ValidationError):
            self._register(self.partner, section=self.outside_section)

    def test_registration_creates_attendance_for_existing_events(self):
        # the core workflow: events exist first, joining creates one
        # 'maybe' row per event (used to be a write() diff on
        # gig.project, now just the create hook)
        event_1 = self._create_event('2026-06-01')
        event_2 = self._create_event('2026-06-15')
        self._register(self.partner)
        attendances = self.env['gig.attendance'].search([
            ('partner_id', '=', self.partner.id),
            ('project_id', '=', self.project.id),
        ])
        self.assertEqual(len(attendances), 2)
        self.assertEqual(attendances.event_id, event_1 | event_2)
        self.assertTrue(all(a.status == 'maybe' for a in attendances))

    def test_reregistration_skips_existing_attendance(self):
        """Attendance survives a registration's deletion (the RSVP
        history is real data), so re-registering a returning musician
        must only create the missing rows - recreating them all would
        trip the unique constraint and make re-registration impossible.
        """
        self._create_event('2026-07-01')
        registration = self._register(self.partner)
        registration.unlink()
        self._register(self.partner)  # must not raise
        self.assertEqual(
            self.env['gig.attendance'].search_count([
                ('partner_id', '=', self.partner.id),
                ('project_id', '=', self.project.id),
            ]),
            1,
        )

    def test_deleting_partner_cascades_to_registrations(self):
        partner = self.env['res.partner'].create({'name': 'Temporary Musician'})
        registration = self._register(partner)
        partner.unlink()
        self.assertFalse(registration.exists())

    def test_deleting_project_cascades_to_registrations(self):
        project = self.env['gig.project'].create({
            'name': 'Short Lived Registration Tour',
            'section_group_id': self.group.id,
        })
        registration = self.env['gig.project.participant'].create({
            'project_id': project.id,
            'partner_id': self.partner.id,
            'section_id': self.section.id,
        })
        project.unlink()
        self.assertFalse(registration.exists())

    def test_cannot_delete_section_used_by_registration(self):
        self._register(self.partner)
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self.section.unlink()
            self.env.flush_all()

    def test_changing_project_group_with_stray_registrations_raises(self):
        """The project-side mirror of the section-in-group rule:
        constrains only react to their own model's fields, so swapping
        the project's group would slip past the participant-side check
        - gig.project's own constraint has to catch it.
        """
        self._register(self.partner)
        empty_group = self.env['gig.section.group'].create(
            {'name': 'Test Fixture Groupless Layout'})
        with self.assertRaises(ValidationError):
            self.project.section_group_id = empty_group
