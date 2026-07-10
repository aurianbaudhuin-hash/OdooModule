from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class GigEvent(models.Model):
    """A single concert or rehearsal date belonging to a project/tour.

    Rehearsals and concerts share this one model (distinguished by
    `event_type`) rather than being split into two models, since they
    share every field except whether a name is allowed - splitting them
    would duplicate the whole schema for one boolean-ish difference.
    """
    _name = 'gig.event'
    _description = 'Individual gig or rehearsal date'
    _order = 'event_date, start_time'

    name = fields.Char(
        string="Name",
        help="Optional",
    )
    event_date = fields.Date(string="Date", required=True)
    # required=True with no explicit default deliberately sidesteps the
    # "is 0.0 midnight, or just not filled in yet?" ambiguity a Float
    # time field would otherwise have - see _check_times below, which
    # relies on these always holding a real value once the record exists.
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
        # 'cascade': an event has no meaning outside its parent project -
        # deleting the project should take its events with it.
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
        """A rehearsal must never carry a name.

        The form view already hides the name field once event_type is
        'rehearsal' (invisible="event_type == 'rehearsal'"), but per this
        codebase's convention that's UX only - the actual guarantee has
        to live here, at the model level, so it also holds for writes
        that bypass the form entirely (imports, other code, etc.).
        """
        for event in self:
            if event.event_type == 'rehearsal' and event.name:
                raise ValidationError(_("A rehearsal cannot have a name."))

    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        """Both times must fall within a single day (0:00 up to, but not
        including, 24:00), and the event must actually end after it
        starts. A Float field can technically hold any number, so
        nothing besides this constraint keeps start_time/end_time
        confined to a sane single-day range.
        """
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
        """Odoo 17+: override this method (instead of the old name_get())
        to control how a record is labeled in Many2one widgets, breadcrumbs, etc.

        A rehearsal always renders as "Rehearsal — <date>" (it can never
        have a name, per _check_name_by_type above). A concert uses its
        name if it has one, otherwise falls back to "Concert — <date>".
        The event_date-missing fallback ("no date") is effectively
        unreachable for a persisted record, since event_date is
        required=True - create() would already have failed before this
        compute could ever run without one.

        @api.depends must list every field read below (event_type, name,
        event_date) - without it the cached display_name doesn't get
        invalidated when those fields change within the same transaction.
        """
        for event in self:
            date_str = event.event_date or _("no date")
            if event.event_type == 'rehearsal':
                event.display_name = _("Rehearsal — %s") % date_str
            else:
                event.display_name = event.name or (_("Concert — %s") % date_str)
