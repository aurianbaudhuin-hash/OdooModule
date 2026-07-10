from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class GigEvent(models.Model):
    _name = 'gig.event'
    _description = 'Individual gig or rehearsal date'
    _order = 'event_date, start_time'
    name = fields.Char(
        string="Name",
        help="Optional",
    )
    event_date = fields.Date(string="Date", required=True)
    start_time = fields.Float(string="Start Time", required=True)
    end_time = fields.Float(string="End Time", required=True)
    location = fields.Char(string="Location")
    notes = fields.Text(string="Comment")
    event_type = fields.Selection(
        selection=[
            ('rehearsal', 'Rehearsal'),
            ('concert', 'Concert'),
        ],
        string="Type",
        required=True,
        default='concert',
        )
    project_id = fields.Many2one(
        comodel_name='gig.project',
        string="Project",
        required=True,
        ondelete='cascade',
        )
    attendance_ids = fields.One2many(
        comodel_name='gig.attendance',
        inverse_name='event_id',
        string="Attendances",
    )
       
    @api.onchange('event_type')
    def _onchange_event_type(self):
        """Clear the name as soon as the user switches to 'rehearsal',
        so the form never lets an inconsistent value linger before saving."""
        if self.event_type == 'rehearsal':
            self.name = False
    @api.constrains('name', 'event_type')
    def _check_name_by_type(self):
        for event in self:
            if event.event_type == 'rehearsal' and event.name:
                raise ValidationError(_("A rehearsal cannot have a name."))
            
    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        for event in self:
            for value, label in (
                (event.start_time, _("start time")),
                (event.end_time, _("end time")),
            ):
                if not (0 <= value < 24):
                    raise ValidationError(_(
                        "The %s must be between 0:00 and 23:59."
                    ) % label)
            if event.end_time <= event.start_time:
                raise ValidationError(_("The end time must be after the start time"))
        
    def _compute_display_name(self):
        """Odoo 17+: override this method (instead of the old name_get())
        to control how a record is labeled in Many2one widgets, breadcrumbs, etc."""
        for event in self:
            date_str = event.event_date or _("no date")
            if event.event_type == 'rehearsal':
                event.display_name = _("Rehearsal — %s") % date_str
            else:
                event.display_name = event.name or (_("Concert — %s") % date_str)
    