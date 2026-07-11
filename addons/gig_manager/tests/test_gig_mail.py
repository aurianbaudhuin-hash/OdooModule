"""Tests for the mail integration: the confirmation email queued on
acceptance (recap + callsheet link), the refusal email queued on
rejection, and the collective "callsheet updated" notification (one
mail per participant with an email, skipping the others). All three
assert on the mail.mail queue records - force_send is False everywhere,
so queuing IS the observable outcome (actual SMTP delivery belongs to
Odoo's mail cron, not to this module).
"""
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGigMail(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        violin = cls.env['gig.instrument'].create(
            {'name': 'Test Fixture Mail Violin'})
        cls.section = cls.env['gig.section'].create({
            'name': 'Test Fixture Mail Strings',
            'instrument_line_ids': [
                Command.create({'instrument_id': violin.id, 'quantity': 4}),
            ],
        })
        cls.group = cls.env['gig.section.group'].create(
            {'name': 'Test Fixture Mail Orchestra'})
        cls.env['gig.section.group.line'].create({
            'group_id': cls.group.id,
            'section_id': cls.section.id,
        })
        cls.project = cls.env['gig.project'].create({
            'name': 'Mail Test Tour',
            'section_group_id': cls.group.id,
        })
        cls.rehearsal = cls.env['gig.event'].create({
            'project_id': cls.project.id,
            'event_type': 'rehearsal',
            'event_date': '2026-11-01',
            'start_time': 19.0,
            'end_time': 21.0,
        })

    def _create_registration(self):
        return self.env['gig.registration'].create({
            'project_id': self.project.id,
            'name': 'Mail Test Musician',
            'email': 'mail.musician@example.com',
            'section_id': self.section.id,
            'attendance_line_ids': [Command.create({
                'event_id': self.rehearsal.id,
                'status': 'present',
            })],
        })

    def _mails_to(self, email):
        return self.env['mail.mail'].search([('email_to', '=', email)])

    def test_accept_queues_confirmation_email(self):
        """Accepting must queue one mail to the address *from the form*
        (the freshest one the musician gave), rendered from the
        editable template: dynamic subject, recap of the registration
        (name, section, availability) and the callsheet link."""
        registration = self._create_registration()
        registration.partner_id = self.env['res.partner'].create(
            {'name': 'Mail Test Musician'})
        registration.action_accept()

        mails = self._mails_to('mail.musician@example.com')
        self.assertEqual(len(mails), 1)
        self.assertIn('Mail Test Tour', mails.subject)
        self.assertIn('Registration confirmed', mails.subject)
        body = mails.body_html
        self.assertIn('Mail Test Musician', body)
        self.assertIn('Test Fixture Mail Strings', body)
        # The availability recap: the declared 'present' on the
        # rehearsal date must be rendered, proving the t-foreach over
        # attendance_line_ids works.
        self.assertIn('Present', body)
        self.assertIn(self.rehearsal.event_date.strftime('%A %d %B %Y'), body)
        # The button must point at the *absolute* callsheet URL - a
        # relative path would be dead in an email client.
        self.assertIn(self.project.get_callsheet_url(), body)
        self.assertTrue(self.project.get_callsheet_url().startswith('http'))

    def test_reject_queues_refusal_email(self):
        registration = self._create_registration()
        registration.action_reject()

        mails = self._mails_to('mail.musician@example.com')
        self.assertEqual(len(mails), 1)
        self.assertIn('Mail Test Tour', mails.subject)
        self.assertIn('unable to offer you a spot', mails.body_html)
        # No callsheet invitation for a refused candidate.
        self.assertNotIn(self.project.get_callsheet_url(), mails.body_html)

    def test_notify_callsheet_update_mails_each_participant(self):
        """The collective notification: one individual mail per
        participant with an email (so nobody sees the other recipients),
        participants without an address skipped without failing, and
        the returned notification tells the organizer both counts."""
        with_mail_1 = self.env['res.partner'].create(
            {'name': 'Reachable One', 'email': 'reachable.one@example.com'})
        with_mail_2 = self.env['res.partner'].create(
            {'name': 'Reachable Two', 'email': 'reachable.two@example.com'})
        without_mail = self.env['res.partner'].create(
            {'name': 'Unreachable Musician'})
        for partner in (with_mail_1, with_mail_2, without_mail):
            self.env['gig.project.participant'].create({
                'project_id': self.project.id,
                'partner_id': partner.id,
                'section_id': self.section.id,
            })

        action = self.project.action_notify_callsheet_update()

        for email, name in [('reachable.one@example.com', 'Reachable One'),
                            ('reachable.two@example.com', 'Reachable Two')]:
            mails = self._mails_to(email)
            self.assertEqual(len(mails), 1)
            self.assertIn('Callsheet updated', mails.subject)
            # Personalized greeting from the sending context - the part
            # a naive partner_to blast couldn't do.
            self.assertIn(name, mails.body_html)
            self.assertIn(self.project.get_callsheet_url(), mails.body_html)
        self.assertEqual(action['tag'], 'display_notification')
        self.assertIn('2', action['params']['message'])
        self.assertIn('1', action['params']['message'])

    def test_notify_callsheet_update_without_recipients_raises(self):
        """All participants unreachable (or none at all) must raise
        instead of silently 'sending' nothing - the organizer would
        otherwise believe the orchestra was notified."""
        with self.assertRaises(UserError):
            self.project.action_notify_callsheet_update()

    def test_accept_survives_deleted_template(self):
        """The email is a courtesy, the state change is the business
        action: with the template gone, accepting must still work and
        simply send nothing."""
        self.env.ref('gig_manager.mail_template_registration_accepted').unlink()
        registration = self._create_registration()
        registration.partner_id = self.env['res.partner'].create(
            {'name': 'No Template Musician'})
        registration.action_accept()
        self.assertEqual(registration.state, 'accepted')
        self.assertFalse(self._mails_to('mail.musician@example.com'))
