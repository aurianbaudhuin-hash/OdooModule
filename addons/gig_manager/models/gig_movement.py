from odoo import models, fields


class GigMovement(models.Model):
    """Reference list of artistic/musical movements (Baroque, Classical,
    Romantic, Impressionist...).

    Same shape and same reasoning as `gig.instrument` and
    `gig.piece.type`: a controlled vocabulary, this time for
    `gig.composer.movement_id`, so a composer's stylistic period is
    picked from a fixed list rather than typed freely.
    """
    _name = 'gig.movement'
    _description = 'Artistic movement / musical style (Baroque, Romantic, etc.)'
    _order = 'name'

    name = fields.Char(string="Name", required=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', "This artistic movement already exists."),
    ]
