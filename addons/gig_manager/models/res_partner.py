from odoo import models, fields
class ResPartner(models.Model):
    _inherit = 'res.partner'
    instrument_ids = fields.One2many(
        comodel_name='gig.partner.instrument',
        inverse_name='partner_id',
        string="Instruments Played",
    )
    gig_project_ids = fields.Many2many(
        comodel_name='gig.project',
        relation='gig_project_partner_rel',
        column1='partner_id',
        column2='project_id',
        string="Gig Projects",
    )
    gig_attendance_ids = fields.One2many(
        comodel_name='gig.attendance',
        inverse_name='partner_id',
        string="Rehearsal Attendances",
    )