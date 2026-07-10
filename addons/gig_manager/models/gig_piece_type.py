from odoo import models, fields


class GigPieceType(models.Model):
    """Reference list of musical piece categories (symphony, concerto,
    string quartet...).

    Same shape and same reasoning as `gig.instrument`: a controlled
    vocabulary for `gig.piece.piece_type_id` so the piece catalogue stays
    consistent instead of accumulating near-duplicate free-text values.
    """
    _name = 'gig.piece.type'
    _description = 'Type of musical piece (symphony, concerto, etc.)'
    _order = 'name'

    name = fields.Char(string="Name", required=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', "This piece type already exists."),
    ]
