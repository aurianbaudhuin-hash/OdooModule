"""Tests for gig.registration + gig.registration.resolve + gig.page.block:
the candidate-partner search (exact email, format-tolerant phone, name
tokens), the accept workflow (partner required, participant + RSVP
creation, duplicate protection), reject, the resolve wizard's conflict
handling (mandatory choice, form-wins update, silent fill of missing
data) and create-contact path, the section-fill helper behind the
"section is full" warning, and the page block CHECK constraint.
"""
import psycopg2

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestGigRegistration(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.violin = cls.env['gig.instrument'].create(
            {'name': 'Test Fixture Web Violin'})
        # Capacity of 2 on purpose: small enough for the fill tests to
        # saturate it with two participants.
        cls.section = cls.env['gig.section'].create({
            'name': 'Test Fixture Web Strings',
            'instrument_line_ids': [
                Command.create({'instrument_id': cls.violin.id, 'quantity': 2}),
            ],
        })
        cls.outside_section = cls.env['gig.section'].create({
            'name': 'Test Fixture Web Outside Section',
            'instrument_line_ids': [
                Command.create({'instrument_id': cls.violin.id, 'quantity': 1}),
            ],
        })
        cls.group = cls.env['gig.section.group'].create(
            {'name': 'Test Fixture Web Orchestra'})
        cls.env['gig.section.group.line'].create({
            'group_id': cls.group.id,
            'section_id': cls.section.id,
        })
        cls.project = cls.env['gig.project'].create({
            'name': 'Web Registration Tour',
            'section_group_id': cls.group.id,
        })
        cls.rehearsal = cls.env['gig.event'].create({
            'project_id': cls.project.id,
            'event_type': 'rehearsal',
            'event_date': '2026-09-01',
            'start_time': 19.0,
            'end_time': 21.0,
        })
        cls.concert = cls.env['gig.event'].create({
            'project_id': cls.project.id,
            'event_type': 'concert',
            'name': 'Web Tour Finale',
            'event_date': '2026-09-15',
            'start_time': 20.0,
            'end_time': 22.0,
        })

    def _create_registration(self, **overrides):
        values = {
            'project_id': self.project.id,
            'name': 'Web Test Musician',
            'email': 'web.musician@example.com',
            'phone': '+32 470 12 34 56',
            'section_id': self.section.id,
            'attendance_line_ids': [Command.create({
                'event_id': self.rehearsal.id,
                'status': 'absent',
            })],
        }
        values.update(overrides)
        return self.env['gig.registration'].create(values)

    def _make_wizard(self, registration):
        # with_context + default_get is exactly what the "Resolve
        # Contact" button does - going through it (rather than passing
        # candidate_ids by hand) keeps the pre-populated candidate list
        # under test too.
        Wizard = self.env['gig.registration.resolve'].with_context(
            default_registration_id=registration.id)
        return Wizard.create(Wizard.default_get(list(Wizard.fields_get())))

    # ------------------------------------------------------------------
    # Candidate search
    # ------------------------------------------------------------------

    def test_candidates_include_same_email_case_insensitive(self):
        """Hard requirement: every contact with the same email MUST be
        found. Emails are case-insensitive identifiers, so a case
        difference must not hide the match."""
        partner = self.env['res.partner'].create({
            'name': 'Unrelated Name',
            'email': 'WEB.MUSICIAN@example.com',
        })
        registration = self._create_registration()
        self.assertIn(partner, registration._find_candidate_partners())

    def test_candidates_include_same_phone_across_formats(self):
        """Hard requirement: every contact with the same phone MUST be
        found - even though '+32 470 12 34 56' and '0470/12.34.56' are
        the same number in different notations, which is why matching
        compares digits (and tolerates the international prefix), not
        strings."""
        partner = self.env['res.partner'].create({
            'name': 'Unrelated Name',
            'email': 'other@example.com',
            'phone': '0470/12.34.56',
        })
        registration = self._create_registration()
        self.assertIn(partner, registration._find_candidate_partners())

    def test_candidates_include_partial_name_match(self):
        """Best-effort fuzzy layer: a contact whose name shares a word
        with the registered name surfaces too - 'Web Test Musician'
        must find 'Musician, Webby' even with different email/phone."""
        partner = self.env['res.partner'].create({
            'name': 'Musician, Webby',
            'email': 'unrelated@example.com',
        })
        registration = self._create_registration()
        self.assertIn(partner, registration._find_candidate_partners())

    # ------------------------------------------------------------------
    # Accept / reject workflow
    # ------------------------------------------------------------------

    def test_accept_without_partner_raises(self):
        """Acceptance creates business records (participant +
        attendance) that need an unambiguous contact - so it must be
        impossible before the resolve step has linked one."""
        registration = self._create_registration()
        with self.assertRaises(UserError):
            registration.action_accept()

    def test_accept_creates_participant_and_applies_rsvps(self):
        """The full happy path: accept turns the staging record into a
        real participant (which auto-creates 'maybe' attendance rows
        for every event), then overlays the musician's actual answers
        from the form - so the rehearsal they declined is 'absent'
        while the concert they weren't asked about stays 'maybe'."""
        registration = self._create_registration()
        partner = self.env['res.partner'].create({'name': 'Accepted Musician'})
        registration.partner_id = partner
        registration.action_accept()

        self.assertEqual(registration.state, 'accepted')
        participant = self.env['gig.project.participant'].search([
            ('project_id', '=', self.project.id),
            ('partner_id', '=', partner.id),
        ])
        self.assertEqual(len(participant), 1)
        self.assertEqual(participant.section_id, self.section)
        rehearsal_att = self.env['gig.attendance'].search([
            ('partner_id', '=', partner.id),
            ('event_id', '=', self.rehearsal.id),
        ])
        concert_att = self.env['gig.attendance'].search([
            ('partner_id', '=', partner.id),
            ('event_id', '=', self.concert.id),
        ])
        self.assertEqual(rehearsal_att.status, 'absent')
        self.assertEqual(concert_att.status, 'maybe')

    def test_accept_existing_participant_raises(self):
        """A registration resolved to someone already participating must
        be blocked with a readable error, not crash into
        gig.project.participant's unique constraint."""
        partner = self.env['res.partner'].create({'name': 'Twice Musician'})
        self.env['gig.project.participant'].create({
            'project_id': self.project.id,
            'partner_id': partner.id,
            'section_id': self.section.id,
        })
        registration = self._create_registration()
        registration.partner_id = partner
        with self.assertRaises(UserError):
            registration.action_accept()

    def test_reject_sets_state_and_creates_nothing(self):
        registration = self._create_registration()
        registration.action_reject()
        self.assertEqual(registration.state, 'rejected')
        self.assertFalse(self.env['gig.project.participant'].search([
            ('project_id', '=', self.project.id),
        ]))

    def test_registration_section_outside_group_raises(self):
        """Same guarantee as on gig.project.participant, but here it
        also shields the public endpoint against forged POST data - the
        web form only offers valid sections, an attacker's POST can
        claim anything."""
        with self.assertRaises(ValidationError):
            self._create_registration(section_id=self.outside_section.id)

    # ------------------------------------------------------------------
    # Resolve wizard
    # ------------------------------------------------------------------

    def test_wizard_prefills_candidates(self):
        partner = self.env['res.partner'].create({
            'name': 'Prefill Candidate',
            'email': 'web.musician@example.com',
        })
        wizard = self._make_wizard(self._create_registration())
        self.assertIn(partner, wizard.candidate_ids)

    def test_link_with_unresolved_conflict_raises(self):
        """When form and contact genuinely disagree on a field, linking
        without an explicit choice must fail: silently preferring
        either side would sometimes destroy the correct value, and only
        the organizer can know which side is right."""
        partner = self.env['res.partner'].create({
            'name': 'Web Test Musician',
            'email': 'old.address@example.com',
        })
        wizard = self._make_wizard(self._create_registration())
        wizard.partner_id = partner
        self.assertTrue(wizard.email_differs)
        with self.assertRaises(UserError):
            wizard.action_link_contact()

    def test_link_form_choice_updates_partner(self):
        """The 'musician changed email' scenario the whole flow exists
        for: choosing the form's value on the email conflict must
        update the existing contact in the database."""
        partner = self.env['res.partner'].create({
            'name': 'Web Test Musician',
            'email': 'old.address@example.com',
            'phone': '+32 470 12 34 56',
        })
        registration = self._create_registration()
        wizard = self._make_wizard(registration)
        wizard.partner_id = partner
        wizard.email_choice = 'form'
        wizard.action_link_contact()
        self.assertEqual(partner.email, 'web.musician@example.com')
        self.assertEqual(registration.partner_id, partner)

    def test_link_fills_missing_partner_data_without_choice(self):
        """An empty field on the contact is not a conflict: the form
        providing data the contact lacked (here: no phone on record)
        must be applied silently, with no pointless arbitration."""
        partner = self.env['res.partner'].create({
            'name': 'Web Test Musician',
            'email': 'web.musician@example.com',
        })
        wizard = self._make_wizard(self._create_registration())
        wizard.partner_id = partner
        self.assertFalse(wizard.phone_differs)
        wizard.action_link_contact()
        self.assertEqual(partner.phone, '+32 470 12 34 56')

    def test_create_contact_links_new_partner(self):
        """The create path: a brand-new contact built from the form
        data, linked to the registration, and handed back as a form
        action so the organizer can complete it (instruments etc. -
        data the public form deliberately doesn't ask for)."""
        registration = self._create_registration()
        wizard = self._make_wizard(registration)
        action = wizard.action_create_contact()
        partner = registration.partner_id
        self.assertTrue(partner)
        self.assertEqual(partner.name, 'Web Test Musician')
        self.assertEqual(partner.email, 'web.musician@example.com')
        self.assertEqual(action['res_model'], 'res.partner')
        self.assertEqual(action['res_id'], partner.id)

    # ------------------------------------------------------------------
    # Section fill + page blocks
    # ------------------------------------------------------------------

    def test_section_fill_counts_only_participants(self):
        """The 'full' flag behind the public warning popup: capacity
        comes from the section's headcount, occupancy from *accepted*
        participants only - a pile of pending registrations must not
        mark a section full, since the organizer may reject them all."""
        self._create_registration()  # pending: must not count
        fill = self.project._get_section_fill()
        self.assertEqual(fill[self.section]['count'], 0)
        self.assertEqual(fill[self.section]['capacity'], 2)
        self.assertFalse(fill[self.section]['full'])

        for index in range(2):
            partner = self.env['res.partner'].create(
                {'name': 'Filler Musician %d' % index})
            self.env['gig.project.participant'].create({
                'project_id': self.project.id,
                'partner_id': partner.id,
                'section_id': self.section.id,
            })
        fill = self.project._get_section_fill()
        self.assertEqual(fill[self.section]['count'], 2)
        self.assertTrue(fill[self.section]['full'])

    def test_block_shown_nowhere_raises(self):
        """CHECK(on_registration OR on_callsheet): a block on neither
        page is invisible everywhere except the backend list - almost
        certainly a mistake, so the DB refuses it."""
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self.env['gig.page.block'].create({
                'project_id': self.project.id,
                'title': 'Nowhere Block',
                'on_registration': False,
                'on_callsheet': False,
            })
            self.env.flush_all()

    def test_shared_block_is_one_record(self):
        """'Edit once, changes on both pages' needs no syncing code
        because a shared block IS one record with both flags: filtering
        for either page returns the same object."""
        block = self.env['gig.page.block'].create({
            'project_id': self.project.id,
            'title': 'Shared Block',
            'content': '<p>Shared content</p>',
            'on_registration': True,
            'on_callsheet': True,
        })
        blocks = self.project.page_block_ids
        self.assertIn(block, blocks.filtered('on_registration'))
        self.assertIn(block, blocks.filtered('on_callsheet'))
