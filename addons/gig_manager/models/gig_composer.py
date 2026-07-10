from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class GigComposer(models.Model):
    _name = 'gig.composer'
    _description = 'Composer of a musical piece'
    _order = 'full_name'
    full_name = fields.Char(string="Full Name", required=True)
    birth_date = fields.Date(string="Birth Date")
    death_date = fields.Date(string="Death Date")
    movement_id = fields.Many2one(
        comodel_name='gig.movement',
        string="Artistic Movement",
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
        for composer in self:
            if composer.birth_date and composer.death_date \
                    and composer.death_date < composer.birth_date:
                raise ValidationError(_(
                    "%(name)s cannot have a date of death earlier than their date of birth."
                ) % {'name': composer.full_name})
    
    @api.depends('full_name')
    def _compute_display_name(self):
        # Without this @api.depends, display_name's cached value survives a
        # write to full_name within the same transaction (it's a non-stored
        # computed field, and Odoo only invalidates the cache for fields
        # declared as dependencies) - stale labels in breadcrumbs/many2ones
        # until the next request. Declaring the dependency fixes that.
        for composer in self:
            composer.display_name = composer.full_name