from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class GigPiece(models.Model):
    """A single musical work (e.g. a symphony, a concerto movement) that
    can be programmed into one or more projects/tours.
    """
    _name = 'gig.piece'
    _description = 'Musical piece'
    _order = 'title'

    title = fields.Char(string="Title", required=True)
    composer_id = fields.Many2one(
        comodel_name='gig.composer',
        string="Composer",
        required=True,
        # 'restrict': a composer with pieces attached must not be
        # deletable - the piece would either be orphaned or silently
        # destroyed, neither of which is acceptable for catalogue data.
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
        # Explicit relation/column1/column2 (rather than letting Odoo
        # auto-generate them) so this M2M and gig.project.piece_ids both
        # point at the exact same pivot table and can be queried from
        # either side - this codebase's convention for any M2M that needs
        # to be filtered/joined from both models.
        relation='gig_project_piece_rel',
        column1='piece_id',
        column2='project_id',
        string="Performed In",
    )

    @api.constrains('composition_year', 'composer_id')
    def _check_composition_year(self):
        """A piece cannot have been composed before its composer was born,
        or after they died.

        The guard below (`if not piece.composition_year or not
        piece.composer_id: continue`) means this check is skipped
        whenever composition_year is falsy - which includes 0, not just
        an actually-empty value. In practice 0 is never a real
        composition year, so this is a harmless quirk rather than a bug
        worth fixing, but it's worth knowing: composition_year=0 silently
        bypasses this constraint regardless of the composer's lifespan.
        It's also skipped whenever the composer's birth_date/death_date
        aren't set, since there's nothing to compare against then.
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
        """Renders as "Composer - Title" when a composer is set, so a
        piece is recognisable in Many2one widgets/breadcrumbs without
        having to open it; falls back to just the title when there's no
        composer yet (e.g. a piece being filled in). The dotted dependency
        `composer_id.full_name` means renaming the composer correctly
        refreshes this piece's display_name too, not just changing
        composer_id itself.
        """
        for piece in self:
            if piece.composer_id:
                piece.display_name = f"{piece.composer_id.full_name} - {piece.title}"
            else:
                piece.display_name = piece.title
