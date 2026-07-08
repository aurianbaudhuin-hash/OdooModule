from odoo import models, fields


class GigEvent(models.Model):
    _name = 'gig.event'
    _description = 'Individual gig or rehearsal date'

    name = fields.Char(string="Name", required=True)
    event_date = fields.Date(string="Date")
    event_type = fields.Selection(
        selection=[
            ('rehearsal', 'Rehearsal'),
            ('concert', 'Concert'),
        ],
        string="Type",
        required=True,
        default='concert',
    )

    project_id = fields.Many2one(
        comodel_name='gig.project',
        string="Project",
        ondelete='cascade',
    )