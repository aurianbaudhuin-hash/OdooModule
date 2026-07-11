from odoo import models, fields


class GigPageBlock(models.Model):
    """One content block on a project's public pages: a title plus
    free-form HTML (styled text, images, embedded maps...), authored by
    the organizer in the backend and rendered read-only on the public
    registration page and/or the participants' callsheet.

    A block *is* the sharing mechanism: on_registration/on_callsheet
    decide where it shows, and a block ticking both simply renders on
    both pages from the same record - so "edit once, changes
    everywhere" holds by construction instead of needing any syncing
    code between two copies. The built-in programme and calendar are
    NOT blocks: they're rendered from the project's own data and always
    present, per the spec's "by default" requirement - blocks are only
    for the organizer's custom additions.
    """
    _name = 'gig.page.block'
    _description = 'Content block on a project public page'
    # Same handle-ordered pattern as gig.section.group.line. One shared
    # sequence across both pages: a block on both keeps one position,
    # which is also the least surprising behaviour when toggling a
    # page checkbox on an existing block.
    _order = 'sequence, id'

    sequence = fields.Integer(string="Sequence", default=10)
    project_id = fields.Many2one(
        comodel_name='gig.project',
        string="Project",
        required=True,
        ondelete='cascade',
    )
    title = fields.Char(string="Title", required=True)
    # sanitize=False is a deliberate trade-off: the default sanitizer
    # strips <iframe>, which would kill the "maps integration" use
    # case. The risk is contained because only internal users
    # (base.group_user, per the ACL) can write blocks - this is
    # organizer-authored content, not user-generated input. Revisit if
    # block editing is ever exposed to a wider group.
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
        # A block shown nowhere is dead data the organizer can't see
        # anywhere but the backend list - most likely a mistake, so the
        # DB refuses it outright. Simple single-row invariant => CHECK
        # constraint, per this codebase's convention.
        ('shown_somewhere', 'CHECK(on_registration OR on_callsheet)',
         "A block must be shown on at least one page: the registration "
         "page, the callsheet, or both."),
    ]
