from odoo import models, fields


class GigAttendance(models.Model):
    """Junction model: one musician's RSVP status for one event, filled
    in ahead of time.

    Per this codebase's convention, this is a pure link model with no
    menu of its own - reached only through the models it links (embedded
    in gig.event's form, gig.project's inline "Attendance" tab, or the
    project-level "Attendance" smart button/standalone filtered list),
    never as a top-level menu entry.
    """
    _name = 'gig.attendance'
    _description = "A musician's attendance status for a gig or rehearsal"

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Musician",
        required=True,
        # 'cascade': a row is meaningless without the musician it
        # refers to.
        ondelete='cascade',
    )
    event_id = fields.Many2one(
        comodel_name='gig.event',
        string="Event",
        required=True,
        # 'cascade': a row is meaningless without the event it refers to.
        ondelete='cascade',
    )
    project_id = fields.Many2one(
        # Derived from the event rather than stored independently, so it
        # can never drift out of sync with event_id.project_id - moving
        # this row to a different event automatically updates project_id
        # too, with no extra code needed (related fields' dependency
        # graph is inferred from the dotted path itself, unlike a
        # `compute=` method, which needs an explicit @api.depends).
        related='event_id.project_id',
        string="Project",
        store=True,
        # readonly=True since this is purely derived - editing it
        # directly wouldn't make sense (it would either be immediately
        # overwritten by the next recompute, or contradict event_id).
        # It exists as a stored column specifically so it can be
        # filtered/grouped on (gig.project.attendance_ids, the
        # attendance search view's group-by-project) without joining
        # through gig.event on every query.
        readonly=True,
    )
    status = fields.Selection(
        selection=[
            ('present', 'Present'),
            ('absent', 'Absent'),
            ('maybe', 'Uncertain'),
        ],
        string="Status",
        required=True,
        # Rows are created ahead of the event (see gig.project.write()),
        # before anyone has actually confirmed whether they're coming -
        # 'maybe' is the only honest default in that situation.
        default='maybe',
    )
    comment = fields.Text(string="Comment")

    _sql_constraints = [
        # A musician can only have one RSVP status per event - a second
        # row for the same pair would just be an ambiguous duplicate.
        ('partner_event_unique', 'unique(partner_id, event_id)',
         "This musician already has an attendance line for this event."),
    ]
