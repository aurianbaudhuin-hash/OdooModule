"""Tests for the res.partner extension: instrument_ids,
gig_participation_ids and gig_attendance_ids are pure inverses of
relations defined elsewhere in this module, and gig_project_ids is
derived from the participations - so these tests verify each one stays
correctly in sync with its "other side" rather than testing any
standalone logic in res_partner.py (there isn't any).
"""
from odoo import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestResPartner(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # gig.project.section_group_id is required, and registering a
        # participant needs a section inside that layout - which layout
        # and section they are is irrelevant to these mirror tests.
        cls.section = cls.env['gig.section'].create({
            'name': 'Test Fixture Partner Strings',
            'instrument_line_ids': [Command.create({
                'instrument_id': cls.env['gig.instrument'].create(
                    {'name': 'Test Fixture Partner Violin'}).id,
                'quantity': 4,
            })],
        })
        cls.section_group = cls.env['gig.section.group'].create(
            {'name': 'Test Fixture Partner Test Orchestra'})
        cls.env['gig.section.group.line'].create({
            'group_id': cls.section_group.id,
            'section_id': cls.section.id,
        })

    def test_instrument_ids_inverse_of_partner_instrument(self):
        """instrument_ids is the O2M inverse of
        gig.partner.instrument.partner_id - creating a partner-instrument
        line directly should make it show up on the partner's side too,
        proving the inverse_name wiring is correct."""
        partner = self.env['res.partner'].create({'name': 'Skilled Musician'})
        instrument = self.env['gig.instrument'].create({'name': 'Test Fixture Flute'})
        line = self.env['gig.partner.instrument'].create({
            'partner_id': partner.id,
            'instrument_id': instrument.id,
            'level': 'professional',
        })
        self.assertIn(line, partner.instrument_ids)

    def test_gig_project_ids_derived_from_registrations(self):
        """gig_project_ids used to share a pivot table with the
        project-side M2M; since participation was promoted to a real
        model (gig.project.participant, carrying the section), it's now
        *computed* from the partner's registrations. Registering a
        musician on the project side must therefore still be visible
        from the partner side - through gig_participation_ids (the true
        inverse) and the derived gig_project_ids alike.
        """
        project = self.env['gig.project'].create({
            'name': 'Mirrored Tour',
            'section_group_id': self.section_group.id,
        })
        partner = self.env['res.partner'].create({'name': 'Mirrored Participant'})
        registration = self.env['gig.project.participant'].create({
            'project_id': project.id,
            'partner_id': partner.id,
            'section_id': self.section.id,
        })
        self.assertIn(registration, partner.gig_participation_ids)
        self.assertIn(project, partner.gig_project_ids)

    def test_gig_attendance_ids_inverse_of_attendance(self):
        """gig_attendance_ids is the O2M inverse of
        gig.attendance.partner_id - an attendance row created directly
        should be reachable from the partner's side."""
        project = self.env['gig.project'].create({
            'name': 'Attendance Mirror Tour',
            'section_group_id': self.section_group.id,
        })
        event = self.env['gig.event'].create({
            'project_id': project.id,
            'event_type': 'concert',
            'event_date': '2026-12-01',
            'start_time': 19.0,
            'end_time': 21.0,
        })
        partner = self.env['res.partner'].create({'name': 'Attendance Mirror Musician'})
        attendance = self.env['gig.attendance'].create({
            'partner_id': partner.id,
            'event_id': event.id,
        })
        self.assertIn(attendance, partner.gig_attendance_ids)
