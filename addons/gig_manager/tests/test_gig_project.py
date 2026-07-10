"""Tests for gig.project: the start_date/end_date compute, the
attendance_count compute (including the recompute-after-write regression
test for the previously-missing @api.depends), action_view_attendance's
returned action dict, the write() override that auto-creates attendance
rows for newly-added participants, and a non-admin ACL sanity check.
"""
from odoo import Command
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestGigProject(TransactionCase):

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
        project = self.env['gig.project'].create({'name': 'Winter Tour'})
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
        project = self.env['gig.project'].create({'name': 'Empty Project'})
        self.assertFalse(project.start_date)
        self.assertFalse(project.end_date)

    def test_attendance_count_reflects_existing_rows(self):
        """attendance_count must match the number of gig.attendance rows
        actually linked to this project, computed via search_count
        rather than len(attendance_ids) - both should agree here."""
        project = self.env['gig.project'].create({'name': 'Count Tour'})
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
        reading it again on the *same* project record right after
        write({'participant_ids': ...}) auto-created attendance rows (see
        the write() test below) would return a stale cached value from
        before those rows existed, because nothing told Odoo the field's
        cache needed invalidating. With the dependency declared, this
        read must reflect the freshly created rows without needing to
        re-browse the record.
        """
        project = self.env['gig.project'].create({'name': 'Fresh Count Tour'})
        self._create_event(project, 'concert', '2026-05-01')
        self.assertEqual(project.attendance_count, 0)
        partner = self.env['res.partner'].create({'name': 'New Participant'})
        project.write({'participant_ids': [Command.set([partner.id])]})
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
        project = self.env['gig.project'].create({'name': 'Button Tour'})
        action = project.action_view_attendance()
        self.assertEqual(action['domain'], [('project_id', '=', project.id)])
        self.assertEqual(action['context']['default_project_id'], project.id)

    def test_write_creates_attendance_for_new_participant(self):
        """The core attendance workflow: events are created first, then
        participants are added to the project afterwards. write() must
        auto-create one 'maybe'-status gig.attendance row per *existing*
        event for each newly added partner, so the organizer doesn't have
        to manually create one row per (partner, event) pair by hand.

        [Command.set([...])] is used rather than a raw (6, 0, [...])
        tuple because that's what the web client's many2many_tags widget
        actually sends (a full replace), making this the most realistic
        way to exercise the write() override. Note it's a *list*
        containing one command, not the bare command tuple - a
        Many2many field's vals entry is always a list of commands, even
        when there's only one.
        """
        project = self.env['gig.project'].create({'name': 'Spring Tour'})
        event_1 = self._create_event(project, 'rehearsal', '2026-06-01')
        event_2 = self._create_event(project, 'concert', '2026-06-15')
        partner = self.env['res.partner'].create({'name': 'New Violinist'})

        project.write({'participant_ids': [Command.set([partner.id])]})

        attendances = self.env['gig.attendance'].search([
            ('partner_id', '=', partner.id),
            ('project_id', '=', project.id),
        ])
        self.assertEqual(len(attendances), 2)
        self.assertEqual(set(attendances.mapped('event_id.id')), {event_1.id, event_2.id})
        self.assertTrue(all(a.status == 'maybe' for a in attendances))

    def test_write_without_participant_change_creates_nothing(self):
        """write() only reacts when 'participant_ids' is actually present
        in vals - an unrelated field write (e.g. renaming the project)
        must not create or touch any attendance rows at all."""
        project = self.env['gig.project'].create({'name': 'Silent Tour'})
        self._create_event(project, 'concert', '2026-07-01')
        project.write({'name': 'Renamed Tour'})
        self.assertEqual(
            self.env['gig.attendance'].search_count([('project_id', '=', project.id)]),
            0,
        )

    def test_write_captures_old_participants_before_super(self):
        """write() must diff the *old* participant_ids (captured before
        calling super().write()) against the new value - if it read
        project.participant_ids only after super().write() had already
        applied the change, "new_partners = new - old" would always
        compute an empty set, since by then old and new would be
        identical, and no attendance would ever be created. This test
        re-writes participant_ids to the *same* single partner a second
        time and confirms no duplicate attendance rows appear - proving
        the diff correctly recognises "already present" partners as not
        new, which only works if the pre-write state was captured
        correctly the first time.
        """
        project = self.env['gig.project'].create({'name': 'Idempotent Tour'})
        self._create_event(project, 'concert', '2026-08-01')
        partner = self.env['res.partner'].create({'name': 'Returning Musician'})

        project.write({'participant_ids': [Command.set([partner.id])]})
        first_count = self.env['gig.attendance'].search_count([('project_id', '=', project.id)])
        self.assertEqual(first_count, 1)

        # Re-applying the same participant list is not "adding" anyone new.
        project.write({'participant_ids': [Command.set([partner.id])]})
        second_count = self.env['gig.attendance'].search_count([('project_id', '=', project.id)])
        self.assertEqual(second_count, 1)

    def test_non_admin_user_can_create_and_read_project(self):
        """security/ir.model.access.csv grants base.group_user full CRUD
        on gig.project. Running every other test as the superuser would
        never actually exercise that ACL row - the superuser bypasses
        access checks entirely - so this test specifically uses a plain
        internal user via with_user() to prove a real non-admin user can
        use the module, not just that the model logic is correct.
        """
        user = new_test_user(self.env, login='gig_test_user', groups='base.group_user')
        project = self.env['gig.project'].with_user(user).create({'name': 'User Created Tour'})
        self.assertEqual(
            self.env['gig.project'].with_user(user).browse(project.id).name,
            'User Created Tour',
        )
