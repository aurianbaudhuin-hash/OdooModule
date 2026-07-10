from odoo import models, fields, api


class GigProject(models.Model):
    """A tour or concert series: the top-level container for a set of
    events (rehearsals/concerts), a programme of pieces, and the
    musicians participating.

    Workflow this model is built around: events are created first by the
    organizer, and participants are added to the project afterwards. See
    write() below for the consequence that has on attendance tracking.
    """
    _name = 'gig.project'
    _description = 'Tour or concert series'

    name = fields.Char(string="Project name", required=True)

    gig_ids = fields.One2many(
        comodel_name='gig.event',
        inverse_name='project_id',
        string="Gigs",
    )

    start_date = fields.Date(
        string="Start date",
        compute='_compute_dates',
        store=True,
        help="Date of the first rehearsal in this project.",
    )
    end_date = fields.Date(
        string="End date",
        compute='_compute_dates',
        store=True,
        help="Date of the last concert in this project.",
    )

    piece_ids = fields.Many2many(
        comodel_name='gig.piece',
        # Explicit relation/column1/column2 so this M2M and
        # gig.piece.project_ids share the exact same pivot table and can
        # be queried/filtered from either side (this codebase's
        # convention for any M2M needing bidirectional access).
        relation='gig_project_piece_rel',
        column1='project_id',
        column2='piece_id',
        string="Programme",
    )

    participant_ids = fields.Many2many(
        comodel_name='res.partner',
        # Same convention as piece_ids above: shared pivot table
        # (gig_project_partner_rel) with res.partner.gig_project_ids, so
        # a contact's projects can be read straight off their own record.
        relation='gig_project_partner_rel',
        column1='project_id',
        column2='partner_id',
        string="Participants",
    )

    attendance_ids = fields.One2many(
        comodel_name='gig.attendance',
        # gig.attendance.project_id is itself a related/stored field
        # (derived from event_id.project_id), not a plain Many2one - but
        # since it's store=True it's a real column, so it works as a
        # one2many inverse exactly like an ordinary Many2one would.
        inverse_name='project_id',
        string="Attendance",
    )

    attendance_count = fields.Integer(
        string="Attendance Count",
        compute='_compute_attendance_count',
    )

    @api.depends('gig_ids.event_date', 'gig_ids.event_type')
    def _compute_dates(self):
        """start_date/end_date intentionally aren't a simple min/max
        across every event: start_date is the earliest *rehearsal* date
        and end_date is the latest *concert* date, matching the intended
        "rehearse first, then perform" lifecycle of a project. A project
        with no matching events on one side (e.g. no rehearsals yet)
        gets False for that date rather than an arbitrary fallback.
        """
        for project in self:
            rehearsal_dates = project.gig_ids.filtered(
                lambda g: g.event_type == 'rehearsal' and g.event_date
            ).mapped('event_date')
            concert_dates = project.gig_ids.filtered(
                lambda g: g.event_type == 'concert' and g.event_date
            ).mapped('event_date')

            project.start_date = min(rehearsal_dates) if rehearsal_dates else False
            project.end_date = max(concert_dates) if concert_dates else False

    @api.depends('attendance_ids')
    def _compute_attendance_count(self):
        # search_count() re-reads the DB every call, but the *cached result*
        # of this compute is only invalidated when a listed dependency
        # changes. attendance_ids is the real O2M behind those attendance
        # rows, so depending on it keeps the badge accurate right after
        # write() (below) creates new attendance lines in the same
        # transaction - without this, the count would look stale until the
        # next request re-triggers the compute from scratch.
        for project in self:
            project.attendance_count = self.env['gig.attendance'].search_count(
                [('project_id', '=', project.id)]
            )

    def action_view_attendance(self):
        """Open the shared gig.attendance list, scoped to this project.

        Complements (doesn't replace) the inline "Attendance" tab on this
        project's own form: this action offers the richer, filterable/
        groupable cross-event view (grouped by event by default, with
        Present/Absent/Uncertain filters), whereas the inline tab is for
        quick at-a-glance editing without leaving the project.
        """
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'gig_manager.action_gig_attendance'
        )
        action['domain'] = [('project_id', '=', self.id)]
        action['context'] = {'default_project_id': self.id}
        return action

    def write(self, vals):
        """Auto-create a 'maybe'-status attendance line for every existing
        event whenever a new partner is added to participant_ids.

        This exists because of the workflow this model assumes: events
        are created first, participants are added afterwards - so without
        this override, adding a musician to a project wouldn't give them
        an attendance row for any of the events already planned, and the
        organizer would have to create those rows by hand one by one.

        old_participants MUST be captured before calling super().write():
        by the time super().write() returns, participant_ids already
        reflects the new value, so diffing "new - old" afterwards would
        always yield an empty set and no attendance would ever be
        created. There's intentionally no equivalent hook on
        gig.event.create() - in this workflow, events are never added
        after registration has started, so that hook was removed as dead
        code rather than kept "just in case".
        """
        old_participants = {
            project: project.participant_ids for project in self
        } if 'participant_ids' in vals else {}

        result = super().write(vals)

        if 'participant_ids' in vals:
            for project in self:
                new_partners = project.participant_ids - old_participants[project]
                for partner in new_partners:
                    for event in project.gig_ids:
                        self.env['gig.attendance'].create({
                            'partner_id': partner.id,
                            'event_id': event.id,
                        })
        return result
