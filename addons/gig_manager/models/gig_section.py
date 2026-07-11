from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class GigSection(models.Model):
    """One section of an ensemble ("First violin", "Flute & Piccolo"...),
    made up of one or more instruments, each with a required headcount.

    A section is shared reference data, like gig.instrument: it is
    defined once and can appear in any number of section groups ("First
    violin = 12 players" can serve both a "Symphony Orchestra" and an
    "Opera Pit" layout). The section does NOT know its position in any
    group - ordering is a property of the (group, section) pair, so it
    lives on gig.section.group.line, the ordered through-model that
    ties the two together.
    """
    _name = 'gig.section'
    _description = 'Ensemble section (instruments with required headcount)'
    _order = 'name'

    name = fields.Char(string="Name", required=True)

    instrument_line_ids = fields.One2many(
        comodel_name='gig.section.instrument',
        inverse_name='section_id',
        string="Instruments",
    )

    # Inverse of the group/section through-model. Mostly here so views
    # and code can ask "which groups use this section?" - e.g. the
    # project form filters selectable sections with a dotted domain on
    # this field ([('group_line_ids.group_id', '=', ...)]).
    group_line_ids = fields.One2many(
        comodel_name='gig.section.group.line',
        inverse_name='section_id',
        string="Used in Groups",
    )

    musician_count = fields.Integer(
        string="Musicians",
        compute='_compute_musician_count',
        help="Total headcount required for this section.",
    )

    @api.depends('instrument_line_ids.quantity')
    def _compute_musician_count(self):
        for section in self:
            section.musician_count = sum(
                section.instrument_line_ids.mapped('quantity')
            )

    @api.constrains('name', 'instrument_line_ids')
    def _check_has_instrument_lines(self):
        """A section is *defined* as one or more instruments with a
        headcount, so an empty section is invalid data, not just an
        unfinished form. Per this codebase's convention the guarantee
        lives here at the model level - the form merely makes it
        convenient to fill the lines in, and a view could never enforce
        this against imports or other code anyway.

        'name' is deliberately listed in the decorator even though the
        check never reads it: @api.constrains only fires for fields
        actually present in the create/write vals, so a constraint on
        instrument_line_ids alone would never run for a section created
        *without* that key - precisely the case it must catch. Since
        name is required, it appears in every create's vals, which
        guarantees this check runs on every new section.
        """
        for section in self:
            if not section.instrument_line_ids:
                raise ValidationError(_(
                    "A section must contain at least one instrument. "
                    "Add an instrument line to '%s' or delete the section.",
                    section.name,
                ))

    _sql_constraints = [
        # Global uniqueness, like the other reference-data models: since
        # sections are shared across groups, two sections with the same
        # name would be indistinguishable in every dropdown that offers
        # them (group lines, project participant registration).
        ('name_unique', 'unique(name)', "This section already exists."),
    ]
