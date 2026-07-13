from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class GigComposer(models.Model):
    """A composer. No custom "nationality" model: res.country already
    exists in core, no point remodelling it.
    """
    _name = 'gig.composer'
    _description = 'Composer of a musical piece'
    _order = 'full_name'

    full_name = fields.Char(string="Full Name", required=True)
    # both optional: living composers have no death_date, and sometimes
    # the birth date just isn't documented
    birth_date = fields.Date(string="Birth Date")
    death_date = fields.Date(string="Death Date")
    movement_id = fields.Many2one(
        comodel_name='gig.movement',
        string="Artistic Movement",
        # restrict: don't let someone delete a movement that composers
        # still reference
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
        # only comparable when both dates are known
        for composer in self:
            if composer.birth_date and composer.death_date \
                    and composer.death_date < composer.birth_date:
                raise ValidationError(_(
                    "%(name)s cannot have a date of death earlier than their date of birth."
                ) % {'name': composer.full_name})

    @api.depends('full_name')
    def _compute_display_name(self):
        """The label is full_name, not a field literally called 'name',
        hence this override (Odoo 17+ way, name_get() is legacy).

        The @api.depends is not optional: without it, renaming a
        composer left stale display_names in the cache until the next
        request. There's a regression test for it.
        """
        for composer in self:
            composer.display_name = composer.full_name
