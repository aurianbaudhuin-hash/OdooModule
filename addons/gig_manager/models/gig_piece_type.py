from odoo import models, fields

class GigPieceType(models.Model):
    _name = 'gig.piece.type'
    _description = 'Type of musical piece (symphony, concerto, etc.)'
    _order = 'name'
    name = fields.Char(string="Name", required=True)
    _sql_constraints = [
        ('name_unique', 'unique(name)', "This piece type already exists."),
]