from odoo import models, fields


class GigAttendance(models.Model):
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
        related='event_id.project_id',
        string="Project",
        store=True,
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
        default='maybe',
    )
    comment = fields.Text(string="Comment")

    _sql_constraints = [
        ('partner_event_unique', 'unique(partner_id, event_id)',
         "This musician already has an attendance line for this event."),
    ]