from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class GigProjectParticipant(models.Model):
    """Membership model: one musician's registration on one project,
    including which section they play in.

    This replaced the plain project<->partner Many2many the day the
    requirement became "every musician in a project is registered in a
    section": a bare M2M row has nowhere to carry the section, so the
    relation had to be promoted to a real model (the same reasoning
    that made gig.partner.instrument a model rather than an M2M between
    partners and instruments - the 'level' needed somewhere to live).

    Per this codebase's convention for link models, no menu of its own:
    registrations are only ever edited from the project's
    "Participants" tab.
    """
    _name = 'gig.project.participant'
    _description = "Musician's registration on a project, with their section"

    project_id = fields.Many2one(
        comodel_name='gig.project',
        string="Project",
        required=True,
        # 'cascade': a registration has no meaning without the project
        # it registers for.
        ondelete='cascade',
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Musician",
        required=True,
        # 'cascade': same reasoning as gig.attendance.partner_id -
        # deleting the contact should take their registrations with
        # them, not block the deletion or leave orphaned rows.
        ondelete='cascade',
    )
    section_id = fields.Many2one(
        comodel_name='gig.section',
        string="Section",
        # Required: this field is the whole reason this model exists -
        # a musician on a project without a section would be exactly
        # the incomplete data this model was introduced to forbid.
        required=True,
        # 'restrict': shared reference data other records depend on.
        ondelete='restrict',
    )

    @api.constrains('project_id', 'section_id')
    def _check_section_in_project_group(self):
        """The section a musician registers in must be part of the
        project's own ensemble layout - registering a 'First violin'
        player on a project whose section group has no first violins
        is a data-entry error, not a valid edge case. The view's domain
        on section_id already filters the dropdown accordingly, but per
        this codebase's convention that's UX only; the guarantee lives
        here. (The mirror-image case - changing a *project's* group
        while registrations exist - can't fire this constraint, since
        no field of this model changes; gig.project has its own
        @api.constrains covering that side.)
        """
        for registration in self:
            group = registration.project_id.section_group_id
            if registration.section_id not in group.line_ids.section_id:
                raise ValidationError(_(
                    "Section '%(section)s' is not part of '%(group)s', "
                    "the section group of project '%(project)s'.",
                    section=registration.section_id.name,
                    group=group.name,
                    project=registration.project_id.name,
                ))

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-create a 'maybe'-status attendance row for every
        existing event of the project a musician registers on.

        This hook used to be a write() override on gig.project that
        diffed old vs. new participant_ids around super().write() -
        promoting the M2M to this model made that diffing machinery
        unnecessary: a new registration simply *is* a create here.
        The workflow it serves is unchanged: events are created first,
        participants are added afterwards, so without this the
        organizer would have to create one row per (musician, event)
        pair by hand. There's still intentionally no equivalent hook on
        gig.event.create() - events are never added after registration
        has started in this workflow.

        Only *missing* (partner, event) pairs are created: attendance
        rows deliberately survive a registration's deletion (the RSVP
        history is still real), so re-registering a returning musician
        must skip the rows they already have rather than tripping the
        unique(partner_id, event_id) constraint.
        """
        registrations = super().create(vals_list)
        for registration in registrations:
            covered_events = self.env['gig.attendance'].search([
                ('partner_id', '=', registration.partner_id.id),
                ('project_id', '=', registration.project_id.id),
            ]).event_id
            for event in registration.project_id.gig_ids - covered_events:
                self.env['gig.attendance'].create({
                    'partner_id': registration.partner_id.id,
                    'event_id': event.id,
                })
        return registrations

    _sql_constraints = [
        # One registration per musician per project: a musician plays
        # in exactly one section of a project, and a second row for the
        # same pair would be an ambiguous duplicate.
        ('project_partner_unique', 'unique(project_id, partner_id)',
         "This musician is already registered on this project. "
         "Edit their existing registration instead of creating a new one."),
    ]
