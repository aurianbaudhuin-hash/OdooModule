from odoo import models, fields


class GigSectionInstrument(models.Model):
    """Junction model: one instrument within a section, with the
    headcount required for it ("12x Violin", "1x Piccolo").

    This is a pure link model - per this codebase's convention it has
    no menu of its own and is only ever reached through its section's
    embedded editable list (inside the section group's form), exactly
    like gig.partner.instrument is only reached through res.partner.
    """
    _name = 'gig.section.instrument'
    _description = 'Instrument headcount within a section'

    section_id = fields.Many2one(
        comodel_name='gig.section',
        string="Section",
        required=True,
        # 'cascade': a headcount line has no meaning without the
        # section it sizes - deleting the section deletes its lines.
        ondelete='cascade',
    )
    instrument_id = fields.Many2one(
        comodel_name='gig.instrument',
        string="Instrument",
        required=True,
        # 'restrict': gig.instrument is reference data other records
        # depend on - deleting an instrument that a section requires
        # must be blocked, not silently erase the section's makeup.
        ondelete='restrict',
    )
    quantity = fields.Integer(
        string="Headcount",
        required=True,
        # Default to the smallest *valid* value rather than 0: the
        # CHECK constraint below rejects 0, so a line saved without
        # touching the field should not be born invalid.
        default=1,
    )

    _sql_constraints = [
        # One line per instrument per section: "12x violin" and another
        # "3x violin" in the same section would be an ambiguous split -
        # edit the existing line's headcount instead.
        ('section_instrument_unique', 'unique(section_id, instrument_id)',
         "This section already has a line for this instrument. "
         "Edit the existing line's headcount instead of creating a new one."),
        # A zero/negative headcount is nonsense data, and this is a
        # simple single-field invariant - so per convention it's a DB
        # CHECK constraint, not an @api.constrains method.
        ('quantity_positive', 'CHECK(quantity > 0)',
         "The headcount must be at least 1."),
    ]
