from odoo import models, fields


class GigInstrument(models.Model):
    """Reference list of musical instruments (Violin, Trumpet, Timpani...).

    This is deliberately a bare lookup table with a single field: it exists
    so `gig.partner.instrument` (which instrument does a contact play, and
    at what level) has a controlled vocabulary to point at, instead of a
    free-text field that would let the same instrument be typed a dozen
    different ways ("cello", "Cello", "violoncelle"...).
    """
    _name = 'gig.instrument'
    _description = 'Musical instrument'
    _order = 'name'

    name = fields.Char(string="Name", required=True)

    _sql_constraints = [
        # DB-level, not just a UI nicety: this is a simple single-field
        # invariant with no cross-field/cross-model logic involved, so it
        # belongs in _sql_constraints rather than an @api.constrains method
        # (per this codebase's convention: SQL constraints for plain
        # uniqueness, Python constraints for anything needing to reason
        # about multiple fields or related records).
        ('name_unique', 'unique(name)', "This instrument already exists."),
    ]
