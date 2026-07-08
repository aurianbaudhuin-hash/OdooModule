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