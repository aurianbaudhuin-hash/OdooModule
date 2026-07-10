from odoo import models, fields


class ResPartner(models.Model):
    """Extends Odoo's standard contact with the gig_manager-specific
    relations: which instruments a contact plays, which projects they
    participate in, and their attendance history.

    All three fields below are pure inverses of relations defined on the
    other side (gig.partner.instrument, gig.project, gig.attendance) -
    nothing is stored here, so this file only ever needs to change if a
    new relation to res.partner is introduced elsewhere in the module.
    """
    _inherit = 'res.partner'

    instrument_ids = fields.One2many(
        comodel_name='gig.partner.instrument',
        inverse_name='partner_id',
        string="Instruments Played",
    )
    gig_project_ids = fields.Many2many(
        comodel_name='gig.project',
        # Same pivot table as gig.project.participant_ids
        # (gig_project_partner_rel), with column1/column2 swapped to
        # match this model being on the "partner" side - this is what
        # lets both models read/filter the same underlying join table
        # without any extra syncing code.
        relation='gig_project_partner_rel',
        column1='partner_id',
        column2='project_id',
        string="Gig Projects",
    )
    gig_attendance_ids = fields.One2many(
        comodel_name='gig.attendance',
        inverse_name='partner_id',
        string="Rehearsal Attendances",
    )
