from odoo import models, fields


class GigMovement(models.Model):
    """Lookup table for artistic movements (Baroque, Romantic,
    Impressionist...), used by gig.composer.movement_id. Same idea as
    gig.instrument.
    """
    _name = 'gig.movement'
    _description = 'Artistic movement / musical style (Baroque, Romantic, etc.)'
    _order = 'name'

    name = fields.Char(string="Name", required=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', "This artistic movement already exists."),
    ]
