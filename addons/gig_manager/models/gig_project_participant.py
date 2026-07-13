from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class GigProjectParticipant(models.Model):
    """One musician's registration on one project, with their section.

    Used to be a plain project<->partner M2M until the requirement
    became "every musician plays in a section" - the link needed a
    payload, so it became a model (same story as gig.partner.instrument
    and its level field).

    Link model, no menu - edited from the project's Participants tab.
    """
    _name = 'gig.project.participant'
    _description = "Musician's registration on a project, with their section"

    project_id = fields.Many2one(
        comodel_name='gig.project',
        string="Project",
        required=True,
        ondelete='cascade',
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Musician",
        required=True,
        # cascade: same as gig.attendance.partner_id - deleting the
        # contact takes their registrations along
        ondelete='cascade',
    )
    section_id = fields.Many2one(
        comodel_name='gig.section',
        string="Section",
        # required - this field is the reason the model exists
        required=True,
        ondelete='restrict',
    )

    @api.constrains('project_id', 'section_id')
    def _check_section_in_project_group(self):
        """The section has to exist in the project's own layout. The
        view's domain already filters the dropdown, but that's UX -
        this is the actual rule. (Changing the *project's* group can't
        fire this one, gig.project has the mirror constraint for that.)
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
        """Auto-create 'maybe' attendance for every existing event when
        a musician joins.

        This used to be a write() override on gig.project diffing old
        vs new participant_ids - once participation became its own
        model, "someone joined" is just a create here, no diffing.
        Still no matching hook on gig.event.create(): in this workflow
        events are never added after registration has started.

        Only the missing (partner, event) pairs get created: attendance
        survives a registration's deletion on purpose (the RSVP history
        is real data), so re-registering a returning musician must not
        trip the unique constraint on the rows they already have.
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
        # a musician plays in exactly one section of a project
        ('project_partner_unique', 'unique(project_id, partner_id)',
         "This musician is already registered on this project. "
         "Edit their existing registration instead of creating a new one."),
    ]
