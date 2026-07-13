from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression


def _phone_digits(phone):
    # digits only, so "+32 470 12 34 56" and "0470/12.34.56" become
    # comparable. Module-level: the wizard and the tests use it too.
    return ''.join(ch for ch in (phone or '') if ch.isdigit())


def _phones_match(phone_a, phone_b):
    """Same line, probably. Raw string comparison misses every
    formatting variant, and real international normalization is a
    rabbit hole - comparing the last 9 digits (subscriber part in most
    plans) handles the +32 vs 0 prefix case well enough. Minimum 6
    digits on both sides so short garbage can't match everything.
    """
    digits_a, digits_b = _phone_digits(phone_a), _phone_digits(phone_b)
    if len(digits_a) < 6 or len(digits_b) < 6:
        return False
    return digits_a[-9:] == digits_b[-9:]


class GigRegistration(models.Model):
    """A registration request from the public form.

    Staging record, not a direct write into gig.project.participant: a
    real participant needs a res.partner, and the person typing might
    already exist in the DB under an old email. So the raw form data
    lands here as 'pending', the organizer resolves it to a contact
    (gig.registration.resolve) and then accepts or rejects. Rejected
    ones keep their data.
    """
    _name = 'gig.registration'
    _description = 'Public registration request for a project'
    _order = 'id desc'

    project_id = fields.Many2one(
        comodel_name='gig.project',
        string="Project",
        required=True,
        ondelete='cascade',
    )
    name = fields.Char(string="Name", required=True)
    email = fields.Char(string="Email", required=True)
    phone = fields.Char(string="Phone")
    section_id = fields.Many2one(
        comodel_name='gig.section',
        string="Section",
        required=True,
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
        # set through the resolve wizard only (readonly in the view) -
        # picking it by hand would skip the duplicate search and the
        # conflict handling. set null: contact gone before acceptance
        # just means the registration is unresolved again.
        ondelete='set null',
    )

    @api.constrains('project_id', 'section_id')
    def _check_section_in_project_group(self):
        # same rule as on gig.project.participant. The public form only
        # offers valid sections, but a public endpoint will get forged
        # POSTs eventually - this is the actual guard.
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
        """Contacts that might be this person, for the resolve wizard.

        Hard requirement: anyone with the same email or phone MUST show
        up (a musician re-registering with a new email but same phone
        has to surface their old record, and vice versa). Name matching
        is best-effort on top: any word of 3+ letters (below that,
        'de'/'la' would match half the database).

        Phone can't go through a search domain - the same number can be
        stored in any format - so contacts with a phone get compared
        digit-wise in Python. Fine at this scale; with a huge contact
        table I'd precompute a sanitized phone column instead.
        """
        self.ensure_one()
        domains = []
        if self.email:
            # =ilike: exact address, case-insensitive. Substring
            # matching on an email would just add noise.
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
        """Pending + resolved -> participant.

        Gated on partner_id: accepting creates business records and
        those need an unambiguous contact, which only the resolve step
        gives. Creating the participant fires its create() hook (the
        'maybe' attendance rows), then the musician's actual answers
        from the form are written over them - the two mechanisms stack
        instead of duplicating each other.
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
        self._send_state_email('gig_manager.mail_template_registration_accepted')

    def action_reject(self):
        for registration in self:
            if registration.state != 'pending':
                raise UserError(_("Only pending registrations can be rejected."))
        self.write({'state': 'rejected'})
        self._send_state_email('gig_manager.mail_template_registration_rejected')

    def _send_state_email(self, template_xmlid):
        """Queue the accept/reject notification.

        force_send stays at its default (False): the mail goes to the
        outgoing queue and the cron delivers - a broken SMTP setup
        should never make accept/reject fail. Same idea behind
        raise_if_not_found=False: the state change is the business
        action, the email is a courtesy, a deleted template shouldn't
        block anything.
        """
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        if not template:
            return
        for registration in self:
            template.send_mail(registration.id)


class GigRegistrationAttendance(models.Model):
    """One rehearsal RSVP inside a registration - the staging twin of
    gig.attendance (no res.partner exists yet at submission time). On
    acceptance these statuses get copied onto the real rows.
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
        # cascade: an answer about a deleted event is useless, and
        # blocking event deletion over staging data would be backwards
        ondelete='cascade',
    )
    # same selection as gig.attendance.status - acceptance copies these
    # across 1:1
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
