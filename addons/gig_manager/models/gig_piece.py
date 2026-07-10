from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class GigPiece(models.Model):
    _name = 'gig.piece'
    _description = 'Musical piece'
    _order = 'title'
    title = fields.Char(string="Title", required=True)
    composer_id = fields.Many2one(
        comodel_name='gig.composer',
        string="Composer",
        required=True,
        ondelete='restrict',
    )
    composition_year = fields.Integer(string="Composition Year", required=True)
    catalog_number = fields.Char(
        string="Catalog Number",
        help="E.g. K. 550, BWV 1049, Op. 27 No. 2. Optional.",
    )
    piece_type_id = fields.Many2one(
        comodel_name='gig.piece.type',
        string="Piece Type",
        required=True,
        ondelete='restrict',
    )
    project_ids = fields.Many2many(
        comodel_name='gig.project',
        relation='gig_project_piece_rel',
        column1='piece_id',
        column2='project_id',
        string="Performed In",
)
    @api.constrains('composition_year', 'composer_id')
    def _check_composition_year(self):
        for piece in self:
            if not piece.composition_year or not piece.composer_id:
                continue
            composer = piece.composer_id
            if composer.birth_date and piece.composition_year < composer.birth_date.year:
                raise ValidationError(_(
                    "%(piece)s cannot have been composed in %(year)s: "
                    "%(composer)s was not yet born (born %(birth)s)."
                    )%{
                        'piece': piece.title,
                        'year': piece.composition_year,
                        'composer': composer.full_name,
                        'birth': composer.birth_date.year,
                    })
            if composer.death_date and piece.composition_year > composer.death_date.year:
                raise ValidationError(_(
                    "%(piece)s cannot have been composed in %(year)s: "
                    "%(composer)s had already died (died %(death)s)."
                )%{
                    'piece': piece.title,
                    'year': piece.composition_year, 'composer': composer.full_name, 'death': composer.death_date.year,
                })
                
                
    @api.depends('title', 'composer_id.full_name')
    def _compute_display_name(self):
        for piece in self:
            if piece.composer_id:
                piece.display_name = f"{piece.composer_id.full_name} - {piece.title}"
            else:
                piece.display_name = piece.title