from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class GigProject(models.Model):
    """A tour or concert series: the top-level container for a set of
    events (rehearsals/concerts), a programme of pieces, and the
    musicians participating (each registered in a section).

    Workflow this model is built around: events are created first by the
    organizer, and participants are added to the project afterwards. See
    gig.project.participant.create() for the consequence that has on
    attendance tracking.
    """
    _name = 'gig.project'
    _description = 'Tour or concert series'

    name = fields.Char(string="Project name", required=True)

    section_group_id = fields.Many2one(
        comodel_name='gig.section.group',
        string="Section group",
        # Every project must declare which ensemble layout it needs -
        # exactly one. 'restrict' (not 'cascade') because the group is
        # shared reference data, like composer_id on gig.piece: deleting
        # a layout that live projects still rely on must be blocked.
        #
        # NB: on a database that already contains projects, Odoo cannot
        # apply the NOT NULL column constraint until every existing row
        # has been given a group (it logs an error and skips it, while
        # the ORM still enforces required= for anything created or
        # edited from then on). Assign a group to legacy projects, then
        # re-run -u gig_manager to get the DB-level guarantee too.
        required=True,
        ondelete='restrict',
    )

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

    participant_ids = fields.One2many(
        # A One2many of registration records, not an M2M of partners:
        # every musician on a project must be registered in a section,
        # and a bare M2M row has nowhere to carry that section - see
        # gig.project.participant's docstring for the full story.
        comodel_name='gig.project.participant',
        inverse_name='project_id',
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

    page_block_ids = fields.One2many(
        comodel_name='gig.page.block',
        inverse_name='project_id',
        string="Page Blocks",
    )

    registration_ids = fields.One2many(
        comodel_name='gig.registration',
        inverse_name='project_id',
        string="Registrations",
    )

    pending_registration_count = fields.Integer(
        string="Pending Registrations",
        compute='_compute_pending_registration_count',
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

    @api.depends('registration_ids.state')
    def _compute_pending_registration_count(self):
        # Counts only 'pending': the smart button is a to-do badge for
        # the organizer ("N requests waiting on you"), not an archive
        # counter - accepted/rejected ones are still reachable through
        # the same button, just not worth a number.
        for project in self:
            project.pending_registration_count = len(
                project.registration_ids.filtered(lambda r: r.state == 'pending')
            )

    def _get_section_fill(self):
        """Map each section of this project's group to its occupancy:
        {section: {'count': confirmed participants, 'capacity': required
        headcount, 'full': bool}}. Only *accepted* participants count -
        pending registrations reserve nothing, otherwise a burst of
        requests the organizer later rejects would scare real
        candidates away from a section that is actually open.

        Lives on the model (not in the website controller) because
        "is this section full?" is a business question, and this way
        backend features can reuse the same definition later.
        """
        self.ensure_one()
        fill = {}
        for section in self.section_group_id.line_ids.section_id:
            count = self.env['gig.project.participant'].search_count([
                ('project_id', '=', self.id),
                ('section_id', '=', section.id),
            ])
            capacity = section.musician_count
            fill[section] = {
                'count': count,
                'capacity': capacity,
                'full': count >= capacity,
            }
        return fill

    def action_view_registrations(self):
        """Open this project's registrations (all states - the domain
        filters by project, the list's own filters handle the rest)."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'gig_manager.action_gig_registration'
        )
        action['domain'] = [('project_id', '=', self.id)]
        action['context'] = {'default_project_id': self.id}
        return action

    def action_open_registration_page(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/gig/%d/register' % self.id,
            'target': 'new',
        }

    def action_open_callsheet_page(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/gig/%d/callsheet' % self.id,
            'target': 'new',
        }

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

    @api.constrains('section_group_id')
    def _check_participants_sections_in_group(self):
        """Mirror image of gig.project.participant's own constraint
        (section must belong to the project's group): that one fires
        when a *registration* is created or edited, but @api.constrains
        only reacts to fields of its own model - so swapping this
        project's section group out from under existing registrations
        would slip past it entirely. This side covers that hole: a
        group change is only valid if every registered musician's
        section still exists in the new layout.
        """
        for project in self:
            stray = project.participant_ids.filtered(
                lambda r: r.section_id not in
                project.section_group_id.line_ids.section_id
            )
            if stray:
                raise ValidationError(_(
                    "Cannot use section group '%(group)s' on project "
                    "'%(project)s': the following musicians are "
                    "registered in sections it does not contain: "
                    "%(names)s.",
                    group=project.section_group_id.name,
                    project=project.name,
                    names=", ".join(stray.partner_id.mapped('name')),
                ))
