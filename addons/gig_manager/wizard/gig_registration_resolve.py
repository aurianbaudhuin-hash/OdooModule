from odoo import models, fields, api, _
from odoo.exceptions import UserError

from odoo.addons.gig_manager.models.gig_registration import _phones_match


class GigRegistrationResolve(models.TransientModel):
    """Dialog that turns a raw registration into a known contact - the
    mandatory step before accepting.

    Two exits:
    - Link: pick one of the suggested candidates. For every field where
      the form and the contact genuinely disagree, an explicit choice
      is required - no silent default, "musician changed email" and
      "musician typoed email" look identical to code.
    - Create: new contact from the form data, then open its form so the
      organizer can complete it (instruments etc. - stuff the public
      form doesn't ask on purpose).

    TransientModel because nothing here deserves to outlive the dialog;
    the outcome gets written on the partner and the registration.
    """
    _name = 'gig.registration.resolve'
    _description = 'Link a registration to a contact, or create one'

    registration_id = fields.Many2one(
        comodel_name='gig.registration',
        string="Registration",
        required=True,
        ondelete='cascade',
    )
    candidate_ids = fields.Many2many(
        comodel_name='res.partner',
        string="Possible Matches",
        readonly=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Contact to Link",
        # no domain restricting to the candidates: they're suggestions,
        # the organizer may recognize someone the search couldn't
        # connect
        help="Pick a suggested match, or search for any other contact.",
    )

    # both sides of each field, so the dialog can show "form says X /
    # contact says Y" next to the choice
    reg_name = fields.Char(related='registration_id.name', string="Form Name")
    reg_email = fields.Char(related='registration_id.email', string="Form Email")
    reg_phone = fields.Char(related='registration_id.phone', string="Form Phone")
    partner_name = fields.Char(related='partner_id.name', string="Contact Name")
    partner_email = fields.Char(related='partner_id.email', string="Contact Email")
    partner_phone = fields.Char(related='partner_id.phone', string="Contact Phone")

    name_differs = fields.Boolean(compute='_compute_differs')
    email_differs = fields.Boolean(compute='_compute_differs')
    phone_differs = fields.Boolean(compute='_compute_differs')

    # no defaults: leaving a real conflict unanswered blocks the link,
    # which is the point
    name_choice = fields.Selection(
        selection=[('existing', 'Keep the contact\'s'), ('form', 'Use the form\'s')],
        string="Name to Keep",
    )
    email_choice = fields.Selection(
        selection=[('existing', 'Keep the contact\'s'), ('form', 'Use the form\'s')],
        string="Email to Keep",
    )
    phone_choice = fields.Selection(
        selection=[('existing', 'Keep the contact\'s'), ('form', 'Use the form\'s')],
        string="Phone to Keep",
    )

    @api.model
    def default_get(self, fields_list):
        # run the candidate search here so the dialog opens already
        # populated - it's the whole reason the wizard exists
        values = super().default_get(fields_list)
        registration_id = values.get('registration_id') \
            or self.env.context.get('default_registration_id')
        if registration_id and 'candidate_ids' in fields_list:
            registration = self.env['gig.registration'].browse(registration_id)
            values['candidate_ids'] = [
                fields.Command.set(registration._find_candidate_partners().ids)
            ]
        return values

    @api.depends('partner_id', 'registration_id')
    def _compute_differs(self):
        """'Differs' only when BOTH sides have a value and disagree.
        One side empty isn't a conflict, just missing data - the link
        action fills that in without bothering anyone. Emails compare
        case-insensitively, phones digit-wise, so pure formatting
        differences don't demand a pointless decision.
        """
        for wizard in self:
            reg, partner = wizard.registration_id, wizard.partner_id
            wizard.name_differs = bool(
                partner and partner.name and reg.name
                and partner.name.strip().lower() != reg.name.strip().lower()
            )
            wizard.email_differs = bool(
                partner and partner.email and reg.email
                and partner.email.strip().lower() != reg.email.strip().lower()
            )
            wizard.phone_differs = bool(
                partner and partner.phone and reg.phone
                and not _phones_match(partner.phone, reg.phone)
            )

    def action_link_contact(self):
        # this is where "musician re-registered with a new email"
        # actually updates the contact in the DB
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("Select the contact to link first."))
        values = {}
        for field, differs, choice in [
            ('name', self.name_differs, self.name_choice),
            ('email', self.email_differs, self.email_choice),
            ('phone', self.phone_differs, self.phone_choice),
        ]:
            form_value = self.registration_id[field]
            if differs:
                if not choice:
                    raise UserError(_(
                        "The form and the contact disagree on the %s - "
                        "choose which value to keep before linking.",
                        field,
                    ))
                if choice == 'form':
                    values[field] = form_value
            elif form_value and not self.partner_id[field]:
                # not a conflict: the contact simply lacked this data
                values[field] = form_value
        if values:
            self.partner_id.write(values)
        self.registration_id.partner_id = self.partner_id
        return {'type': 'ir.actions.act_window_close'}

    def action_create_contact(self):
        # create from the form data, then open the contact so the
        # organizer can fill in the rest (the Music tab is right there)
        self.ensure_one()
        partner = self.env['res.partner'].create({
            'name': self.registration_id.name,
            'email': self.registration_id.email,
            'phone': self.registration_id.phone,
        })
        self.registration_id.partner_id = partner
        return {
            'type': 'ir.actions.act_window',
            'name': _("New Contact"),
            'res_model': 'res.partner',
            'res_id': partner.id,
            'view_mode': 'form',
            'target': 'current',
        }
