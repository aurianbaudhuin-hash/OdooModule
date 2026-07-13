from odoo import models, fields, api


class GigSectionGroup(models.Model):
    """An ordered ensemble layout ("Symphony Orchestra", "Wind Band"...).

    Reference data like gig.instrument: a reusable template that any
    number of projects point at (which is also why deleting one in use
    is restricted, see gig.project.section_group_id).

    No direct link to sections: they're shared, and this group's
    ordering of them can't live on the shared record - hence the
    gig.section.group.line through-model carrying the sequence.
    """
    _name = 'gig.section.group'
    _description = 'Ordered collection of ensemble sections'
    _order = 'name'

    name = fields.Char(string="Name", required=True)

    # no ordering code needed here: an O2M always comes back in the
    # comodel's _order, and the line model orders by sequence
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
        # sum the sections' own computed counts instead of reaching down
        # to the quantities - keeps the headcount math in one place
        for group in self:
            group.musician_count = sum(
                group.line_ids.section_id.mapped('musician_count')
            )

    _sql_constraints = [
        ('name_unique', 'unique(name)', "This section group already exists."),
    ]
