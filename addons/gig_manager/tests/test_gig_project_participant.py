"""Tests for gig.project.participant: the unique(project_id, partner_id)
constraint, the section-must-belong-to-the-project's-group constraint
(on both the registration side and the project side), the create() hook
that auto-creates 'maybe' attendance rows (including its skip-existing
behaviour when a musician re-registers), the cascade deletes from
partner and project, and the 'restrict' protection on the section.
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
        # One section inside the project's group, one deliberately kept
        # outside it - the constraint tests need both.
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
        """_sql_constraints unique(project_id, partner_id): a musician
        plays in exactly one section of a project - a second
        registration for the same pair would be an ambiguous duplicate,
        so it must be blocked at the DB level."""
        self._register(self.partner)
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self._register(self.partner)
            self.env.flush_all()

    def test_section_outside_project_group_raises(self):
        """@api.constrains on (project_id, section_id): the section a
        musician registers in must exist in the project's own ensemble
        layout. The form's domain already filters the dropdown, but per
        this codebase's convention that's UX only - the guarantee lives
        at the model level, where it also catches imports and code."""
        with self.assertRaises(ValidationError):
            self._register(self.partner, section=self.outside_section)

    def test_registration_creates_attendance_for_existing_events(self):
        """The core attendance workflow, relocated: events are created
        first, participants are registered afterwards, and create()
        must give the new musician one 'maybe' attendance row per
        existing event. This hook used to be a write() override on
        gig.project diffing old vs. new participant_ids - promoting the
        M2M to this model turned that diff into a plain create hook."""
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
        """Attendance rows deliberately survive a registration's
        deletion (the RSVP history is still real data), so a returning
        musician's new registration must only create the *missing*
        (partner, event) pairs - blindly recreating them all would trip
        gig.attendance's unique constraint and make re-registering a
        musician impossible."""
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
        """partner_id uses ondelete='cascade' (data with no meaning
        outside its parent, same as gig.attendance.partner_id): deleting
        the contact takes their registrations with them."""
        partner = self.env['res.partner'].create({'name': 'Temporary Musician'})
        registration = self._register(partner)
        partner.unlink()
        self.assertFalse(registration.exists())

    def test_deleting_project_cascades_to_registrations(self):
        """project_id uses ondelete='cascade': a registration has no
        meaning without the project it registers for."""
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
        """section_id uses ondelete='restrict': the section is shared
        reference data - deleting one that musicians are registered in
        must be blocked, not silently erase where they play."""
        self._register(self.partner)
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self.section.unlink()
            self.env.flush_all()

    def test_changing_project_group_with_stray_registrations_raises(self):
        """The project-side mirror of the section-in-group constraint:
        @api.constrains only reacts to fields of its own model, so
        swapping a project's section group out from under existing
        registrations would never fire the registration-side check -
        gig.project's own @api.constrains('section_group_id') has to
        catch it instead."""
        self._register(self.partner)
        empty_group = self.env['gig.section.group'].create(
            {'name': 'Test Fixture Groupless Layout'})
        with self.assertRaises(ValidationError):
            self.project.section_group_id = empty_group
