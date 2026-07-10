from odoo import models, fields

class GigInstrument(models.Model):
    _name = 'gig.instrument'
    _description = 'Musical instrument'
    _order = 'name'
    name = fields.Char(string="Name", required=True)
    _sql_constraints = [
        ('name_unique', 'unique(name)', "This instrument already exists."),
    ]