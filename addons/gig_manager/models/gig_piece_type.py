from odoo import models, fields


class GigPieceType(models.Model):
    """Lookup table for piece categories (symphony, concerto, string
    quartet...). Same idea as gig.instrument: controlled vocabulary for
    gig.piece.piece_type_id.
    """
    _name = 'gig.piece.type'
    _description = 'Type of musical piece (symphony, concerto, etc.)'
    _order = 'name'

    name = fields.Char(string="Name", required=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', "This piece type already exists."),
    ]
