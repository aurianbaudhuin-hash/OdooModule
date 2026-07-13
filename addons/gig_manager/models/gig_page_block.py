from odoo import models, fields


class GigPageBlock(models.Model):
    """A content block on a project's public pages: title + free HTML
    (styled text, images, embedded maps...), written in the backend,
    rendered read-only on the registration page and/or the callsheet.

    The block IS the sharing mechanism: tick both page checkboxes and
    the same record renders on both pages - "edit once, changes
    everywhere" with zero syncing code. The programme and calendar are
    NOT blocks: those come straight from the project's data and are
    always there; blocks are only for custom additions.
    """
    _name = 'gig.page.block'
    _description = 'Content block on a project public page'
    # one shared sequence across both pages - least surprising when
    # toggling a checkbox on an existing block
    _order = 'sequence, id'

    sequence = fields.Integer(string="Sequence", default=10)
    project_id = fields.Many2one(
        comodel_name='gig.project',
        string="Project",
        required=True,
        ondelete='cascade',
    )
    title = fields.Char(string="Title", required=True)
    # sanitize=False, eyes open: the default sanitizer strips <iframe>,
    # which kills embedded maps. Acceptable because only internal users
    # can write blocks (see the ACL) - revisit if block editing ever
    # opens up to a wider group.
    content = fields.Html(string="Content", sanitize=False)
    on_registration = fields.Boolean(
        string="On Registration Page",
        default=True,
        help="Show this block on the public registration page.",
    )
    on_callsheet = fields.Boolean(
        string="On Callsheet",
        help="Show this block on the participants' callsheet.",
    )

    _sql_constraints = [
        # a block shown nowhere is invisible everywhere except the
        # backend list - almost certainly a mistake, refuse it
        ('shown_somewhere', 'CHECK(on_registration OR on_callsheet)',
         "A block must be shown on at least one page: the registration "
         "page, the callsheet, or both."),
    ]
