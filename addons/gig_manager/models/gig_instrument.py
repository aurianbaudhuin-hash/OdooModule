from odoo import models, fields


class GigInstrument(models.Model):
    """Bare lookup table for instruments. Exists so partner/section lines
    point at a controlled list instead of free text ("cello", "Cello",
    "violoncelle"... no thanks).
    """
    _name = 'gig.instrument'
    _description = 'Musical instrument'
    _order = 'name'

    name = fields.Char(string="Name", required=True)

    _sql_constraints = [
        # plain single-field uniqueness -> SQL constraint, no need for
        # an @api.constrains here
        ('name_unique', 'unique(name)', "This instrument already exists."),
    ]
