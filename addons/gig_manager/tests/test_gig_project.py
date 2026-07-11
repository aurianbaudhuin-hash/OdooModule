"""Tests for gig.project: the start_date/end_date compute, the
attendance_count compute (including the recompute regression test for
the previously-missing @api.depends), action_view_attendance's returned
action dict, and a non-admin ACL sanity check. The participant
registration workflow itself (auto-created attendance, constraints)
lives with its model in test_gig_project_participant.py.
"""
from odoo import Command
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestGigProject(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # section_group_id is required on gig.project, so every project
        # created below needs an ensemble layout to point at - and the
        # attendance-recompute test registers a musician, which needs a
        # section inside that layout too. "Test Fixture " prefix per
        # this suite's convention: instrument/section/group names are
        # unique and this runs on odoo_db.
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
        """_compute_dates: start_date is the earliest *rehearsal* date and
        end_date is the latest *concert* date - not simply min/max across
        all events - since the intended lifecycle is "rehearse first, then
        perform". This test uses events out of chronological creation
        order specifically to prove the compute is doing a real min/max
        over event_date, not just picking the first/last created record.
        """
        project = self._create_project('Winter Tour')
        self._create_event(project, 'rehearsal', '2026-01-10')
        self._create_event(project, 'rehearsal', '2026-01-05')  # earlier than above
        self._create_event(project, 'concert', '2026-02-20')
        self._create_event(project, 'concert', '2026-03-01')  # later than above
        self.assertEqual(str(project.start_date), '2026-01-05')
        self.assertEqual(str(project.end_date), '2026-03-01')

    def test_dates_false_when_no_events(self):
        """A brand-new project with no events yet must not crash the
        compute or default to some arbitrary date - both dates should
        simply be False."""
        project = self._create_project('Empty Project')
        self.assertFalse(project.start_date)
        self.assertFalse(project.end_date)

    def test_attendance_count_reflects_existing_rows(self):
        """attendance_count must match the number of gig.attendance rows
        actually linked to this project, computed via search_count
        rather than len(attendance_ids) - both should agree here."""
        project = self._create_project('Count Tour')
        event = self._create_event(project, 'concert', '2026-04-01')
        partner = self.env['res.partner'].create({'name': 'Counted Musician'})
        self.env['gig.attendance'].create({
            'partner_id': partner.id,
            'event_id': event.id,
        })
        self.assertEqual(project.attendance_count, 1)

    def test_attendance_count_recomputes_after_participant_added(self):
        """Regression test for the missing @api.depends('attendance_ids')
        bug that used to sit on _compute_attendance_count.

        attendance_count is a non-stored computed field. Before the fix,
        reading it again on the *same* project record right after a
        registration auto-created attendance rows (see
        test_gig_project_participant.py) would return a stale cached
        value from before those rows existed, because nothing told Odoo
        the field's cache needed invalidating. With the dependency
        declared, this read must reflect the freshly created rows
        without needing to re-browse the record.
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
        """action_view_attendance must open the shared attendance action
        scoped to this project: a domain filter (so the list only shows
        this project's rows) and a default_project_id context key (so a
        new row created from that list is pre-filled with this project).
        Only these two keys are asserted - the rest of the action dict
        comes straight from _for_xml_id() and isn't this method's
        responsibility to get right.
        """
        project = self._create_project('Button Tour')
        action = project.action_view_attendance()
        self.assertEqual(action['domain'], [('project_id', '=', project.id)])
        self.assertEqual(action['context']['default_project_id'], project.id)

    def test_non_admin_user_can_create_and_read_project(self):
        """security/ir.model.access.csv grants base.group_user full CRUD
        on gig.project. Running every other test as the superuser would
        never actually exercise that ACL row - the superuser bypasses
        access checks entirely - so this test specifically uses a plain
        internal user via with_user() to prove a real non-admin user can
        use the module, not just that the model logic is correct.
        """
        user = new_test_user(self.env, login='gig_test_user', groups='base.group_user')
        project = self.env['gig.project'].with_user(user).create({
            'name': 'User Created Tour',
            # Deliberately not using _create_project(): that helper runs
            # as the superuser, and referencing the group here as the
            # plain user also exercises the gig.section.group read ACL.
            'section_group_id': self.section_group.id,
        })
        self.assertEqual(
            self.env['gig.project'].with_user(user).browse(project.id).name,
            'User Created Tour',
        )
