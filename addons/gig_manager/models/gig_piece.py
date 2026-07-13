from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class GigPiece(models.Model):
    """A musical work, programmable into any number of projects."""
    _name = 'gig.piece'
    _description = 'Musical piece'
    _order = 'title'

    title = fields.Char(string="Title", required=True)
    composer_id = fields.Many2one(
        comodel_name='gig.composer',
        string="Composer",
        required=True,
        # restrict: deleting a composer must not orphan/destroy their
        # pieces
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
        # explicit relation/columns so this and gig.project.piece_ids
        # share the same pivot table (queryable from both sides)
        relation='gig_project_piece_rel',
        column1='piece_id',
        column2='project_id',
        string="Performed In",
    )

    @api.constrains('composition_year', 'composer_id')
    def _check_composition_year(self):
        """Composition year must fall within the composer's lifespan
        (when we know it).

        NB: the falsy-check below also skips composition_year == 0.
        0 is never a real year, so not worth special-casing, but keep
        it in mind: year 0 silently bypasses this constraint.
        Compare .year to the int, not the Date object to an int -
        already got bitten by that once.
        """
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
        """"Composer - Title" in dropdowns, just the title while no
        composer is set yet. The dotted dependency matters: renaming a
        composer has to refresh their pieces' labels too.
        """
        for piece in self:
            if piece.composer_id:
                piece.display_name = f"{piece.composer_id.full_name} - {piece.title}"
            else:
                piece.display_name = piece.title
