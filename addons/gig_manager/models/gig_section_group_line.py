from odoo import models, fields


class GigSectionGroupLine(models.Model):
    """Through-model group <-> section: "this section, in this group,
    at this position".

    Why not a plain M2M: nowhere to put the per-group position. Why not
    sequence on the section itself: that would tie each section to one
    group and kill reuse. So: through-model. (Same pattern would apply
    to ordering a project's programme someday.)

    Link model, no menu - edited inside the group's form only.
    """
    _name = 'gig.section.group.line'
    _description = 'Section within a section group, with its position'
    # standard recipe for handle-ordered lines; id as tie-breaker for
    # rows still sharing the default sequence
    _order = 'sequence, id'

    sequence = fields.Integer(
        string="Sequence",
        # nobody types this - the drag handle in the group form
        # rewrites it
        default=10,
    )
    group_id = fields.Many2one(
        comodel_name='gig.section.group',
        string="Section group",
        required=True,
        # cascade: a position entry dies with its group...
        ondelete='cascade',
    )
    section_id = fields.Many2one(
        comodel_name='gig.section',
        string="Section",
        required=True,
        # ...but never takes the shared section down with it - other
        # groups may still use it, hence restrict on this side
        ondelete='restrict',
    )
    # related, not computed: the headcount belongs to the section, this
    # just surfaces it in the group's list
    musician_count = fields.Integer(
        related='section_id.musician_count',
        string="Musicians",
    )

    _sql_constraints = [
        # same section twice in a group = double-counted headcount
        ('group_section_unique', 'unique(group_id, section_id)',
         "This group already contains this section."),
    ]
