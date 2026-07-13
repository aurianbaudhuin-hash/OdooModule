from odoo import models, fields


class GigSectionInstrument(models.Model):
    """One instrument within a section, with its headcount ("12x
    Violin"). Pure link model, only edited through the section's form -
    same deal as gig.partner.instrument.
    """
    _name = 'gig.section.instrument'
    _description = 'Instrument headcount within a section'

    section_id = fields.Many2one(
        comodel_name='gig.section',
        string="Section",
        required=True,
        ondelete='cascade',
    )
    instrument_id = fields.Many2one(
        comodel_name='gig.instrument',
        string="Instrument",
        required=True,
        # restrict: don't let an instrument deletion silently rewrite
        # section compositions
        ondelete='restrict',
    )
    quantity = fields.Integer(
        string="Headcount",
        required=True,
        # default 1, not 0: the CHECK below rejects 0, a line saved
        # without touching the field shouldn't be born invalid
        default=1,
    )

    _sql_constraints = [
        # one line per instrument per section - "12x violin" plus
        # "3x violin" in the same section makes no sense, edit the line
        ('section_instrument_unique', 'unique(section_id, instrument_id)',
         "This section already has a line for this instrument. "
         "Edit the existing line's headcount instead of creating a new one."),
        # simple single-row invariant -> DB CHECK, not python
        ('quantity_positive', 'CHECK(quantity > 0)',
         "The headcount must be at least 1."),
    ]
