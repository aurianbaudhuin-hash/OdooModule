from odoo import models, fields, api


class ResPartner(models.Model):
    """Extends Odoo's standard contact with the gig_manager-specific
    relations: which instruments a contact plays, which projects they
    participate in (via their registrations), and their attendance
    history.

    Nothing is stored here - every field below is either a pure inverse
    of a relation defined on the other side (gig.partner.instrument,
    gig.project.participant, gig.attendance) or derived from one - so
    this file only ever needs to change if a new relation to
    res.partner is introduced elsewhere in the module.
    """
    _inherit = 'res.partner'

    instrument_ids = fields.One2many(
        comodel_name='gig.partner.instrument',
        inverse_name='partner_id',
        string="Instruments Played",
    )
    gig_participation_ids = fields.One2many(
        comodel_name='gig.project.participant',
        inverse_name='partner_id',
        string="Project Registrations",
    )
    gig_project_ids = fields.Many2many(
        comodel_name='gig.project',
        # Computed, not a stored pivot table: this used to share
        # gig_project_partner_rel with gig.project.participant_ids, but
        # participation was promoted from a plain M2M to a real model
        # (gig.project.participant, carrying the musician's section) -
        # so "which projects is this contact on" is now *derived* from
        # their registrations rather than being its own relation that
        # could drift out of sync with them.
        compute='_compute_gig_project_ids',
        string="Gig Projects",
    )
    gig_attendance_ids = fields.One2many(
        comodel_name='gig.attendance',
        inverse_name='partner_id',
        string="Rehearsal Attendances",
    )

    @api.depends('gig_participation_ids.project_id')
    def _compute_gig_project_ids(self):
        for partner in self:
            partner.gig_project_ids = partner.gig_participation_ids.project_id
