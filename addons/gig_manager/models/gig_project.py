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
        help="Date of the first event in this project.",
    )
    end_date = fields.Date(
        string="End date",
        compute='_compute_dates',
        store=True,
        help="Date of the last event in this project.",
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

    @api.depends('gig_ids.event_date')
    def _compute_dates(self):
        for project in self:
            dates = project.gig_ids.filtered(
                lambda g: g.event_date
            ).mapped('event_date')
            
            project.start_date = min(dates) if dates else False
            project.end_date = max(dates) if dates else False