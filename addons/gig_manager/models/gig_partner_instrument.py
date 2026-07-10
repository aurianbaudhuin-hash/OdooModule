from odoo import models, fields


class GigPartnerInstrument(models.Model):
    _name = 'gig.partner.instrument'
    _description = 'Instrument practiced by a contact, with skill level'
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Contact",
        required=True,
        ondelete='cascade',
    )
    instrument_id = fields.Many2one(
        comodel_name='gig.instrument',
        string="Instrument",
        required=True,
        ondelete='restrict',
    )
    level = fields.Selection(
        selection=[
            ('amateur_low', 'Amateur - Low'),
            ('amateur_medium', 'Amateur - Medium'),
            ('amateur_high', 'Amateur - High'),
            ('student', 'Student'),
            ('professional', 'Professional'),
            ('high_level_professional', 'High Level Professional'),
        ],
        string="Level",
        required=True,
)
    _sql_constraints = [
        ('partner_instrument_unique', 'unique(partner_id, instrument_id)',
         "This contact already has an entry for this instrument. "
         "Edit the existing line instead of creating a new one."),
    ]