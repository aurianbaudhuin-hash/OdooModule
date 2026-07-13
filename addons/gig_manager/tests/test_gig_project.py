"""gig.project: date computes, attendance_count (incl. the @api.depends
regression), action_view_attendance, non-admin ACL check. The
registration workflow lives in test_gig_project_participant.py.
"""
from odoo import Command
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestGigProject(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # every project needs a section group, and the recompute test
        # registers a musician so the group needs a section too
        cls.section = cls.env['gig.section'].create({
            'name': 'Test Fixture Project Strings',
            'instrument_line_ids': [Command.create({
                'instrument_id': cls.env['gig.instrument'].create(
                    {'name': 'Test Fixture Project Violin'}).id,
                'quantity': 8,
            })],
        })
        cls.section_group = cls.env['gig.section.group'].create(
            {'name': 'Test Fixture Project Test Orchestra'})
        cls.env['gig.section.group.line'].create({
            'group_id': cls.section_group.id,
            'section_id': cls.section.id,
        })

    def _create_project(self, name):
        return self.env['gig.project'].create({
            'name': name,
            'section_group_id': self.section_group.id,
        })

    def _create_event(self, project, event_type, event_date):
        return self.env['gig.event'].create({
            'project_id': project.id,
            'event_type': event_type,
            'event_date': event_date,
            'start_time': 10.0,
            'end_time': 12.0,
        })

    def test_dates_pick_earliest_rehearsal_and_latest_concert(self):
        # events created out of chronological order, to make sure the
        # compute does a real min/max and doesn't just take the
        # first/last created record
        project = self._create_project('Winter Tour')
        self._create_event(project, 'rehearsal', '2026-01-10')
        self._create_event(project, 'rehearsal', '2026-01-05')  # earlier than above
        self._create_event(project, 'concert', '2026-02-20')
        self._create_event(project, 'concert', '2026-03-01')  # later than above
        self.assertEqual(str(project.start_date), '2026-01-05')
        self.assertEqual(str(project.end_date), '2026-03-01')

    def test_dates_false_when_no_events(self):
        # no events -> False, not a crash or some made-up date
        project = self._create_project('Empty Project')
        self.assertFalse(project.start_date)
        self.assertFalse(project.end_date)

    def test_attendance_count_reflects_existing_rows(self):
        project = self._create_project('Count Tour')
        event = self._create_event(project, 'concert', '2026-04-01')
        partner = self.env['res.partner'].create({'name': 'Counted Musician'})
        self.env['gig.attendance'].create({
            'partner_id': partner.id,
            'event_id': event.id,
        })
        self.assertEqual(project.attendance_count, 1)

    def test_attendance_count_recomputes_after_participant_added(self):
        """Regression for the missing @api.depends('attendance_ids').

        attendance_count is non-stored; before the fix, reading it
        right after a registration auto-created attendance rows gave
        the stale pre-registration value (nothing told the cache to
        invalidate). Must reflect the new rows without re-browsing.
        """
        project = self._create_project('Fresh Count Tour')
        self._create_event(project, 'concert', '2026-05-01')
        self.assertEqual(project.attendance_count, 0)
        partner = self.env['res.partner'].create({'name': 'New Participant'})
        self.env['gig.project.participant'].create({
            'project_id': project.id,
            'partner_id': partner.id,
            'section_id': self.section.id,
        })
        self.assertEqual(project.attendance_count, 1)

    def test_action_view_attendance_domain_and_context(self):
        # only the two keys this method is responsible for - the rest
        # of the dict comes straight from _for_xml_id
        project = self._create_project('Button Tour')
        action = project.action_view_attendance()
        self.assertEqual(action['domain'], [('project_id', '=', project.id)])
        self.assertEqual(action['context']['default_project_id'], project.id)

    def test_non_admin_user_can_create_and_read_project(self):
        """Everything else in the suite runs as admin, which bypasses
        ACLs entirely - this is the one test that actually exercises
        the base.group_user line in ir.model.access.csv.
        """
        user = new_test_user(self.env, login='gig_test_user', groups='base.group_user')
        project = self.env['gig.project'].with_user(user).create({
            'name': 'User Created Tour',
            # not using _create_project(): that helper runs as admin,
            # and referencing the group as the plain user also checks
            # the gig.section.group read ACL
            'section_group_id': self.section_group.id,
        })
        self.assertEqual(
            self.env['gig.project'].with_user(user).browse(project.id).name,
            'User Created Tour',
        )
