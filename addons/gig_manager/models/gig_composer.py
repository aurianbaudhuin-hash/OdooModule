from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class GigComposer(models.Model):
    """A composer of one or more musical pieces.

    Deliberately does not have its own "nationality" model: `country_id`
    reuses Odoo's built-in `res.country`, since that reference data already
    exists and re-modelling it here would just duplicate core Odoo data.
    """
    _name = 'gig.composer'
    _description = 'Composer of a musical piece'
    _order = 'full_name'

    full_name = fields.Char(string="Full Name", required=True)
    # Both dates are optional (not required=True): a composer may still be
    # alive (no death_date) or their exact birth date may simply be
    # unknown/undocumented - this model must stay usable in either case.
    birth_date = fields.Date(string="Birth Date")
    death_date = fields.Date(string="Death Date")
    movement_id = fields.Many2one(
        comodel_name='gig.movement',
        string="Artistic Movement",
        # 'restrict': gig.movement is reference data other records (this
        # composer) depend on - deleting a movement that's still assigned
        # to a composer must be blocked, not silently null it out.
        ondelete='restrict',
    )
    country_id = fields.Many2one(
        comodel_name='res.country',
        string="Nationality",
        ondelete='restrict',
    )
    piece_ids = fields.One2many(
        comodel_name='gig.piece',
        inverse_name='composer_id',
        string="Pieces",
    )

    @api.constrains('birth_date', 'death_date')
    def _check_dates(self):
        """A composer's death cannot precede their own birth.

        Only fires when *both* dates are set (see the `and` chain below) -
        a composer with just one date known, or neither, has nothing to
        compare and must not be blocked by this check.
        """
        for composer in self:
            if composer.birth_date and composer.death_date \
                    and composer.death_date < composer.birth_date:
                raise ValidationError(_(
                    "%(name)s cannot have a date of death earlier than their date of birth."
                ) % {'name': composer.full_name})

    @api.depends('full_name')
    def _compute_display_name(self):
        """Odoo 17+ pattern: override this (instead of the legacy
        name_get()) to control how this record is labeled in Many2one
        widgets, breadcrumbs, etc. Here it's simply the composer's name,
        but it still needs its own compute because `full_name` isn't
        literally a field called `name`.

        Without this @api.depends, display_name's cached value survives a
        write to full_name within the same transaction (it's a non-stored
        computed field, and Odoo only invalidates the cache for fields
        declared as dependencies) - stale labels in breadcrumbs/many2ones
        until the next request. Declaring the dependency fixes that.
        """
        for composer in self:
            composer.display_name = composer.full_name
