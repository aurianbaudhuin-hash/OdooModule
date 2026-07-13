from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class GigProject(models.Model):
    """A tour or concert series: events, a programme, and the musicians
    participating (each registered in a section).

    Assumed workflow: the organizer plans the events first, musicians
    join afterwards - see gig.project.participant.create() for what
    that implies on attendance.
    """
    _name = 'gig.project'
    _description = 'Tour or concert series'

    name = fields.Char(string="Project name", required=True)

    section_group_id = fields.Many2one(
        comodel_name='gig.section.group',
        string="Section group",
        # exactly one ensemble layout per project. restrict, not
        # cascade: the group is shared reference data (same reasoning
        # as composer_id on gig.piece).
        #
        # NB on existing DBs: postgres refuses the NOT NULL while old
        # rows have no group (odoo logs it and moves on, the ORM still
        # enforces required= on new writes). Assign groups to legacy
        # projects, then re-run -u to get the DB constraint too.
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
        # explicit pivot so gig.piece.project_ids maps onto the same
        # table and the relation is queryable from both sides
        relation='gig_project_piece_rel',
        column1='project_id',
        column2='piece_id',
        string="Programme",
    )

    participant_ids = fields.One2many(
        # registration records, not a bare M2M to res.partner: each
        # musician carries their section, an M2M row has nowhere to
        # put that (see gig.project.participant)
        comodel_name='gig.project.participant',
        inverse_name='project_id',
        string="Participants",
    )

    attendance_ids = fields.One2many(
        comodel_name='gig.attendance',
        # the inverse here is a related/stored field on gig.attendance,
        # not a plain M2O - works fine as an O2M inverse because
        # store=True makes it a real column
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
        """Not a plain min/max over all events: start = earliest
        *rehearsal*, end = latest *concert* ("rehearse first, then
        perform"). No events on one side -> False, no made-up fallback.
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
        # the depends on attendance_ids is what keeps the badge fresh
        # right after a registration creates attendance rows in the
        # same transaction - without it the cached value stayed stale
        # until the next request (had that bug, there's a test now)
        for project in self:
            project.attendance_count = self.env['gig.attendance'].search_count(
                [('project_id', '=', project.id)]
            )

    @api.depends('registration_ids.state')
    def _compute_pending_registration_count(self):
        # pending only - this badge is a to-do counter, the accepted/
        # rejected ones are still behind the same button
        for project in self:
            project.pending_registration_count = len(
                project.registration_ids.filtered(lambda r: r.state == 'pending')
            )

    def _get_section_fill(self):
        """Occupancy per section of this project's group:
        {section: {'count', 'capacity', 'full'}}.

        Counts accepted participants only. Pending registrations
        reserve nothing - a pile of requests I might reject shouldn't
        scare candidates away from an open section. On the model rather
        than in the controller because "is this section full" is a
        business question.
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
        # no state filter here, the list's own filters take it from
        # there
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'gig_manager.action_gig_registration'
        )
        action['domain'] = [('project_id', '=', self.id)]
        action['context'] = {'default_project_id': self.id}
        return action

    def get_callsheet_url(self):
        # absolute URL for emails - relative paths are dead in a mail
        # client. get_base_url() reads web.base.url, no hardcoded host.
        self.ensure_one()
        return "%s/gig/%d/callsheet" % (self.get_base_url(), self.id)

    def action_notify_callsheet_update(self):
        """Email every participant that the callsheet changed.

        One mail per musician (template reads the recipient from the
        context) so nobody sees the other addresses. Musicians without
        an email get skipped; all-skipped raises instead of pretending
        the orchestra was notified.
        """
        self.ensure_one()
        template = self.env.ref('gig_manager.mail_template_callsheet_updated')
        recipients = self.participant_ids.partner_id.filtered('email')
        if not recipients:
            raise UserError(_(
                "No participant of this project has an email address - "
                "there is nobody to notify."
            ))
        for partner in recipients:
            template.with_context(
                recipient_email=partner.email,
                recipient_name=partner.name,
            ).send_mail(self.id)
        skipped = len(self.participant_ids) - len(recipients)
        message = _("Callsheet update sent to %s musician(s).", len(recipients))
        if skipped:
            message += _(" (%s participant(s) without an email address were skipped.)", skipped)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'message': message, 'type': 'success', 'sticky': False},
        }

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
        """Smart button: the shared attendance list scoped to this
        project. Complements the inline tab - this one has the filters
        and group-bys, the tab is for quick edits in place.
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
        """Mirror of the check on gig.project.participant. That one only
        fires when a registration's own fields change - swapping the
        *project's* group out from under existing registrations would
        slip right past it, so this side has to exist too.
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
