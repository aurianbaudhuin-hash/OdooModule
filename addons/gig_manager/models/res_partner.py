from odoo import models, fields, api


class ResPartner(models.Model):
    """Extends the standard contact with the gig side: instruments
    played, project registrations, attendance history.

    Nothing is stored here - everything below is an inverse of a
    relation defined elsewhere, or derived from one. This file only
    changes when a new relation to res.partner appears in the module.
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
        # computed, no pivot table: this used to share
        # gig_project_partner_rel with the project-side M2M, but
        # participation got promoted to a real model (section per
        # musician) - so "which projects" is now derived from the
        # registrations instead of a second relation that could drift.
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
