"""res.partner extension: the three gig fields are inverses (or derived
from one), so these tests only check they stay in sync with the other
side - there's no logic in res_partner.py itself.
"""
from odoo import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestResPartner(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # projects need a group, registrations need a section in it -
        # which ones is irrelevant here
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
        partner = self.env['res.partner'].create({'name': 'Skilled Musician'})
        instrument = self.env['gig.instrument'].create({'name': 'Test Fixture Flute'})
        line = self.env['gig.partner.instrument'].create({
            'partner_id': partner.id,
            'instrument_id': instrument.id,
            'level': 'professional',
        })
        self.assertIn(line, partner.instrument_ids)

    def test_gig_project_ids_derived_from_registrations(self):
        # gig_project_ids used to be an M2M sharing a pivot with the
        # project side; it's computed from the registrations now -
        # registering on the project side must still show up here
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
