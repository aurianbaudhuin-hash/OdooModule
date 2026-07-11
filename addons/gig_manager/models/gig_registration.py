from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression


def _phone_digits(phone):
    """Reduce a phone number to its digits, for format-tolerant
    comparison ("+32 470 12 34 56" vs "0470/12.34.56"). Module-level
    helper rather than a model method: it has no dependency on any
    record, and both this model and its tests use it.
    """
    return ''.join(ch for ch in (phone or '') if ch.isdigit())


def _phones_match(phone_a, phone_b):
    """True when two phone numbers plausibly denote the same line.

    Comparing raw strings would miss every formatting variant, and full
    international normalization (country prefixes etc.) is a rabbit
    hole this module doesn't need - so the middle ground: compare the
    last 9 digits (the subscriber part in most numbering plans), which
    makes "+32 470 12 34 56" match "0470 12 34 56". At least 6 digits
    are required on both sides so short garbage can't match everything.
    """
    digits_a, digits_b = _phone_digits(phone_a), _phone_digits(phone_b)
    if len(digits_a) < 6 or len(digits_b) < 6:
        return False
    return digits_a[-9:] == digits_b[-9:]


class GigRegistration(models.Model):
    """A musician's registration request submitted through a project's
    public web form.

    This is deliberately a *staging* record, not a direct write into
    gig.project.participant: a real participant row needs a res.partner,
    and the public form intentionally doesn't know whether the person
    typing already exists in the database (possibly under an old email
    address). So the raw form data lands here in state 'pending', the
    organizer resolves it to a contact (see gig.registration.resolve),
    and only an explicit Accept turns it into a participant + attendance
    rows. Rejected registrations keep their data for the record.
    """
    _name = 'gig.registration'
    _description = 'Public registration request for a project'
    _order = 'id desc'

    project_id = fields.Many2one(
        comodel_name='gig.project',
        string="Project",
        required=True,
        # 'cascade': a registration request has no meaning without the
        # project it applies to.
        ondelete='cascade',
    )
    name = fields.Char(string="Name", required=True)
    email = fields.Char(string="Email", required=True)
    phone = fields.Char(string="Phone")
    section_id = fields.Many2one(
        comodel_name='gig.section',
        string="Section",
        required=True,
        # 'restrict': shared reference data, same as everywhere else.
        ondelete='restrict',
    )
    attendance_line_ids = fields.One2many(
        comodel_name='gig.registration.attendance',
        inverse_name='registration_id',
        string="Rehearsal Availability",
    )
    state = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('accepted', 'Accepted'),
            ('rejected', 'Rejected'),
        ],
        string="Status",
        default='pending',
        required=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Matched Contact",
        # The organizer sets this via the resolve wizard, never by hand
        # on the form (readonly in the view): it must go through the
        # duplicate search / conflict resolution flow.
        # 'set null': if the contact disappears before acceptance, the
        # registration simply becomes unresolved again.
        ondelete='set null',
    )

    @api.constrains('project_id', 'section_id')
    def _check_section_in_project_group(self):
        """Same rule as gig.project.participant: the requested section
        must exist in the project's ensemble layout. The public form
        only offers valid sections, but per this codebase's convention
        that's UX only - this also shields against forged POST data,
        which a public endpoint must assume will happen.
        """
        for registration in self:
            group = registration.project_id.section_group_id
            if registration.section_id not in group.line_ids.section_id:
                raise ValidationError(_(
                    "Section '%(section)s' is not part of '%(group)s', "
                    "the section group of project '%(project)s'.",
                    section=registration.section_id.name,
                    group=group.name,
                    project=registration.project_id.name,
                ))

    def _find_candidate_partners(self):
        """Return contacts that plausibly are the person behind this
        registration, for the resolve wizard to offer.

        The hard requirement is recall on the strong identifiers: every
        contact with the same email or phone number MUST be found (a
        musician who re-registers with a new email but the same phone
        must surface their old record, and vice versa). Name matching
        is best-effort on top: any contact whose name contains one of
        the registered name's words (3+ letters, to keep 'de'/'la' from
        matching half the database).

        Phone can't be matched with a search domain - the same number
        can be stored in any format - so contacts with a phone are
        fetched and compared digit-wise in Python. Fine at this
        module's scale; a mass-contact deployment would precompute a
        sanitized phone column instead.
        """
        self.ensure_one()
        domains = []
        if self.email:
            # =ilike: exact address, case-insensitive - emails are
            # identifiers, substring matching would only add noise.
            domains.append([('email', '=ilike', self.email)])
        for token in (self.name or '').split():
            if len(token) >= 3:
                domains.append([('name', 'ilike', token)])
        candidates = self.env['res.partner']
        if domains:
            candidates = candidates.search(expression.OR(domains))
        if _phone_digits(self.phone):
            with_phone = self.env['res.partner'].search([('phone', '!=', False)])
            candidates |= with_phone.filtered(
                lambda p: _phones_match(p.phone, self.phone)
            )
        return candidates

    def action_open_resolve_wizard(self):
        """Open the contact-resolution wizard for this registration."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Resolve Contact"),
            'res_model': 'gig.registration.resolve',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_registration_id': self.id},
        }

    def action_accept(self):
        """Turn a resolved registration into a real participant row.

        Gated on partner_id on purpose: acceptance is what creates
        business records (participant + attendance), and those need an
        unambiguous contact - which only the resolve step can provide.
        Creating the participant fires gig.project.participant.create(),
        which builds the 'maybe' attendance rows; the musician's actual
        answers from the form are then copied over them, so the two
        mechanisms compose instead of duplicating each other.
        """
        self.ensure_one()
        if self.state != 'pending':
            raise UserError(_("Only pending registrations can be accepted."))
        if not self.partner_id:
            raise UserError(_(
                "Link this registration to a contact first (or create "
                "one from it) - accepting needs to know exactly who is "
                "registering."
            ))
        already = self.env['gig.project.participant'].search([
            ('project_id', '=', self.project_id.id),
            ('partner_id', '=', self.partner_id.id),
        ], limit=1)
        if already:
            raise UserError(_(
                "%(partner)s is already a participant of %(project)s "
                "(section: %(section)s).",
                partner=self.partner_id.name,
                project=self.project_id.name,
                section=already.section_id.name,
            ))
        self.env['gig.project.participant'].create({
            'project_id': self.project_id.id,
            'partner_id': self.partner_id.id,
            'section_id': self.section_id.id,
        })
        for line in self.attendance_line_ids:
            attendance = self.env['gig.attendance'].search([
                ('partner_id', '=', self.partner_id.id),
                ('event_id', '=', line.event_id.id),
            ], limit=1)
            attendance.status = line.status
        self.state = 'accepted'

    def action_reject(self):
        for registration in self:
            if registration.state != 'pending':
                raise UserError(_("Only pending registrations can be rejected."))
        self.write({'state': 'rejected'})


class GigRegistrationAttendance(models.Model):
    """One rehearsal RSVP inside a registration request - the staging
    twin of gig.attendance, needed because no res.partner exists yet at
    submission time. On acceptance these statuses are copied onto the
    real attendance rows the participant creation generates.
    """
    _name = 'gig.registration.attendance'
    _description = 'Rehearsal availability declared on a registration'

    registration_id = fields.Many2one(
        comodel_name='gig.registration',
        string="Registration",
        required=True,
        ondelete='cascade',
    )
    event_id = fields.Many2one(
        comodel_name='gig.event',
        string="Event",
        required=True,
        # 'cascade': an availability answer for a deleted event is
        # meaningless, and blocking event deletion over staging data
        # would be backwards.
        ondelete='cascade',
    )
    # Same selection as gig.attendance.status on purpose: acceptance
    # copies these values across 1:1.
    status = fields.Selection(
        selection=[
            ('present', 'Present'),
            ('absent', 'Absent'),
            ('maybe', 'Uncertain'),
        ],
        string="Status",
        default='maybe',
        required=True,
    )

    _sql_constraints = [
        ('registration_event_unique', 'unique(registration_id, event_id)',
         "This registration already has an answer for this event."),
    ]
