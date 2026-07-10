from odoo import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestResPartner(TransactionCase):

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

    def test_gig_project_ids_mirrors_participant_ids(self):
        """gig_project_ids (on res.partner) and participant_ids (on
        gig.project) are two Many2many fields deliberately pointed at the
        *same* pivot table (gig_project_partner_rel, with matching
        column1/column2 on each side) - this codebase's convention for
        any M2M that needs to be queried from both directions. Adding a
        partner from the project side must be visible from the partner
        side without any extra syncing code, since it's the same
        underlying join table row either way.
        """
        project = self.env['gig.project'].create({'name': 'Mirrored Tour'})
        partner = self.env['res.partner'].create({'name': 'Mirrored Participant'})
        project.write({'participant_ids': [Command.set([partner.id])]})
        self.assertIn(project, partner.gig_project_ids)

    def test_gig_attendance_ids_inverse_of_attendance(self):
        """gig_attendance_ids is the O2M inverse of
        gig.attendance.partner_id - an attendance row created directly
        should be reachable from the partner's side."""
        project = self.env['gig.project'].create({'name': 'Attendance Mirror Tour'})
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
