from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class GigEvent(models.Model):
    """A single concert or rehearsal date.

    One model for both types (event_type selection) - they share every
    field except whether a name is allowed, splitting them would
    duplicate the whole schema for nothing.
    """
    _name = 'gig.event'
    _description = 'Individual gig or rehearsal date'
    _order = 'event_date, start_time'

    name = fields.Char(
        string="Name",
        help="Optional",
    )
    event_date = fields.Date(string="Date", required=True)
    # required on purpose: a Float time of 0.0 could mean "midnight" or
    # "not filled in". Making it required kills the ambiguity - don't
    # test these with truthiness.
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
        # cascade: an event without its project is meaningless
        ondelete='cascade',
    )
    attendance_ids = fields.One2many(
        comodel_name='gig.attendance',
        inverse_name='event_id',
        string="Attendances",
    )

    @api.onchange('event_type')
    def _onchange_event_type(self):
        # clear the name right away when switching to rehearsal, don't
        # wait for the save to complain
        if self.event_type == 'rehearsal':
            self.name = False

    @api.constrains('name', 'event_type')
    def _check_name_by_type(self):
        """Rehearsals don't get names. The view hides the field
        (invisible=...) but that's cosmetic - imports and code skip the
        form, so the real check is here.
        """
        for event in self:
            if event.event_type == 'rehearsal' and event.name:
                raise ValidationError(_("A rehearsal cannot have a name."))

    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        # a Float will happily hold 25.0 or -3, nothing but this keeps
        # the times inside one day and in the right order
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

    @api.depends('event_type', 'name', 'event_date')
    def _compute_display_name(self):
        """Rehearsals render as "Rehearsal — <date>", concerts use their
        name when they have one. The "no date" fallback is basically
        unreachable (event_date is required) but keeps the compute safe
        on drafts.

        The depends has to stay complete - missing one = stale labels
        within the transaction, same bug as the composer rename.
        """
        for event in self:
            date_str = event.event_date or _("no date")
            if event.event_type == 'rehearsal':
                event.display_name = _("Rehearsal — %s") % date_str
            else:
                event.display_name = event.name or (_("Concert — %s") % date_str)
