from odoo import models, fields


class GigAttendance(models.Model):
    """One musician's RSVP for one event, filled in ahead of time.

    Link model, but unlike the other ones it does get its own menu:
    browsing/filtering attendance across projects is actually useful,
    a partner's instrument list isn't.
    """
    _name = 'gig.attendance'
    _description = "A musician's attendance status for a gig or rehearsal"

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Musician",
        required=True,
        ondelete='cascade',
    )
    event_id = fields.Many2one(
        comodel_name='gig.event',
        string="Event",
        required=True,
        ondelete='cascade',
    )
    project_id = fields.Many2one(
        # related, not an independent column: can't drift from
        # event_id.project_id, and moving the row to another event
        # updates it for free - with no @api.depends to forget, unlike
        # the display_name computes
        related='event_id.project_id',
        string="Project",
        # store=True so it's a real column we can filter/group on (and
        # so gig.project.attendance_ids can use it as O2M inverse)
        store=True,
        # derived value, editing it directly would make no sense
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
        # rows are pre-created before anyone confirmed anything, so
        # 'maybe' is the only honest default
        default='maybe',
    )
    comment = fields.Text(string="Comment")

    _sql_constraints = [
        # one RSVP per musician per event
        ('partner_event_unique', 'unique(partner_id, event_id)',
         "This musician already has an attendance line for this event."),
    ]
