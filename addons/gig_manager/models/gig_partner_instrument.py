from odoo import models, fields


class GigPartnerInstrument(models.Model):
    """Junction model: which instrument a contact (res.partner) plays, and
    at what skill level.

    This is a pure link model - per this codebase's convention, it has no
    menu of its own and is only ever reached through res.partner's form
    (as an embedded editable list), never as a standalone top-level list.
    """
    _name = 'gig.partner.instrument'
    _description = 'Instrument practiced by a contact, with skill level'

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Contact",
        required=True,
        # 'cascade': this row has no meaning without the contact it
        # describes - deleting the contact should delete their
        # instrument/skill entries along with them, not block the
        # deletion or leave orphaned rows.
        ondelete='cascade',
    )
    instrument_id = fields.Many2one(
        comodel_name='gig.instrument',
        string="Instrument",
        required=True,
        # 'restrict': gig.instrument is reference data other records
        # depend on - deleting an instrument that a contact has recorded
        # as playing must be blocked, not silently erase that data.
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
        # A contact should have at most one skill-level entry per
        # instrument - the error message below tells the user to edit
        # the existing line rather than create an ambiguous second one.
        ('partner_instrument_unique', 'unique(partner_id, instrument_id)',
         "This contact already has an entry for this instrument. "
         "Edit the existing line instead of creating a new one."),
    ]
