from odoo import models, fields, api


class GigProject(models.Model):
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
        relation='gig_project_piece_rel',
        column1='project_id',
        column2='piece_id',
        string="Programme",
    )

    participant_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='gig_project_partner_rel',
        column1='project_id',
        column2='partner_id',
        string="Participants",
    )

    attendance_ids = fields.One2many(
        comodel_name='gig.attendance',
        inverse_name='project_id',
        string="Attendance",
    )

    attendance_count = fields.Integer(
        string="Attendance Count",
        compute='_compute_attendance_count',
    )

    @api.depends('gig_ids.event_date', 'gig_ids.event_type')
    def _compute_dates(self):
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
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'gig_manager.action_gig_attendance'
        )
        action['domain'] = [('project_id', '=', self.id)]
        action['context'] = {'default_project_id': self.id}
        return action

    def write(self, vals):
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