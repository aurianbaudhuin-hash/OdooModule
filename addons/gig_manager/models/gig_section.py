from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class GigSection(models.Model):
    """An ensemble section ("First violin", "Flute & Piccolo"...): one
    or more instruments, each with a headcount.

    Sections are shared reference data - defined once, usable in any
    number of section groups. That's why there's no group_id/sequence
    here: the position of a section is a property of the (group,
    section) pair and lives on gig.section.group.line.
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

    # inverse of the group/section through-model. Mainly here so views
    # can filter "sections of this project's group" with a dotted
    # domain on it.
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
        """A section with no instruments is not a section. Enforced here
        and not just in the form, imports/code don't go through forms.

        Why 'name' is in the decorator: constrains only fire for fields
        present in the create/write vals, so a create *without*
        instrument_line_ids would never trigger a check on that field
        alone - exactly the case to catch. name is required, so it's in
        every create, which guarantees this runs. Found out via a
        failing test.
        """
        for section in self:
            if not section.instrument_line_ids:
                raise ValidationError(_(
                    "A section must contain at least one instrument. "
                    "Add an instrument line to '%s' or delete the section.",
                    section.name,
                ))

    _sql_constraints = [
        # global uniqueness: sections are shared, two "First Violin"s
        # would be indistinguishable in every dropdown
        ('name_unique', 'unique(name)', "This section already exists."),
    ]
