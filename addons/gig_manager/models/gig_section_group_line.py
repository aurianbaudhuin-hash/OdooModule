from odoo import models, fields


class GigSectionGroupLine(models.Model):
    """Ordered through-model between gig.section.group and gig.section:
    one row = "this section appears in this group, at this position".

    A plain Many2many could link groups to shared sections, but it has
    nowhere to put a per-group position - and a One2many with the
    sequence on gig.section itself would force each section to belong
    to exactly one group, killing reuse. The through-model is the only
    shape that gives both: sections stay shared reference data, and
    each group orders its own lines independently. (This is the same
    pattern CLAUDE.md earmarks for ordering a project's programme.)

    Per this codebase's convention for link models, no menu of its own:
    lines are only ever edited inside the group's form.
    """
    _name = 'gig.section.group.line'
    _description = 'Section within a section group, with its position'
    # 'sequence, id' is the standard Odoo pattern for a user-orderable
    # One2many: the group's form exposes a drag handle on sequence, and
    # the 'id' tie-breaker keeps ordering deterministic between rows
    # that still share the same sequence value.
    _order = 'sequence, id'

    sequence = fields.Integer(
        string="Sequence",
        # default=10 is the usual Odoo convention for handle-ordered
        # lines; users never type this number - dragging rows in the
        # group's form rewrites it.
        default=10,
    )
    group_id = fields.Many2one(
        comodel_name='gig.section.group',
        string="Section group",
        required=True,
        # 'cascade': a position entry has no meaning without the group
        # it orders - deleting the group deletes its lines (but NOT the
        # shared sections they point at, see section_id below).
        ondelete='cascade',
    )
    section_id = fields.Many2one(
        comodel_name='gig.section',
        string="Section",
        required=True,
        # 'restrict': gig.section is shared reference data - deleting a
        # section that some group's layout still includes must be
        # blocked, not silently rewrite that group's composition.
        ondelete='restrict',
    )
    # Related, not computed: the headcount is a property of the section
    # itself; this line only re-exposes it so the group's list can show
    # per-section totals without a click-through.
    musician_count = fields.Integer(
        related='section_id.musician_count',
        string="Musicians",
    )

    _sql_constraints = [
        # The same section twice in one group would be an ambiguous
        # duplicate (and would double-count its headcount).
        ('group_section_unique', 'unique(group_id, section_id)',
         "This group already contains this section."),
    ]
