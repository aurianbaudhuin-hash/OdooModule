from odoo import models, fields, api


class GigSectionGroup(models.Model):
    """An ordered collection of sections describing a full ensemble
    layout ("Symphony Orchestra", "Chamber Orchestra", "Wind Band"...).

    This is reference data in the same spirit as gig.instrument or
    gig.piece.type: a reusable template that projects point at, rather
    than something owned by a single project. Every gig.project carries
    a required Many2one to exactly one group - the project declares
    which ensemble layout it needs, and the same group can be reused
    across as many projects as apply. That reuse is also why deleting a
    group referenced by a project is blocked (ondelete='restrict' on
    gig.project.section_group_id), matching how the other reference
    models are protected.

    The group does not link to sections directly: sections are shared
    reference data, and this group's *ordering* of them can't live on
    the shared record - so the link goes through gig.section.group.line
    (one row per section per group, carrying the sequence).
    """
    _name = 'gig.section.group'
    _description = 'Ordered collection of ensemble sections'
    _order = 'name'

    name = fields.Char(string="Name", required=True)

    # No explicit ordering machinery needed on this side: a One2many is
    # always read back in its comodel's _order, and the line model
    # declares _order = 'sequence, id' - so this field returns lines in
    # the user-arranged order for free.
    line_ids = fields.One2many(
        comodel_name='gig.section.group.line',
        inverse_name='group_id',
        string="Sections",
    )

    musician_count = fields.Integer(
        string="Musicians",
        compute='_compute_musician_count',
        help="Total headcount required across all sections of this group.",
    )

    @api.depends('line_ids.section_id.musician_count')
    def _compute_musician_count(self):
        # Depends on the sections' own computed count rather than
        # reaching through to instrument_line_ids.quantity directly, so
        # the "sum the headcounts" logic lives in exactly one place
        # (gig.section) and this compute is a plain aggregation of it.
        for group in self:
            group.musician_count = sum(
                group.line_ids.section_id.mapped('musician_count')
            )

    _sql_constraints = [
        # Same convention as the other reference-data models
        # (gig.instrument, gig.piece.type, gig.movement): plain
        # single-field uniqueness belongs at the DB level in
        # _sql_constraints, not in an @api.constrains method.
        ('name_unique', 'unique(name)', "This section group already exists."),
    ]
