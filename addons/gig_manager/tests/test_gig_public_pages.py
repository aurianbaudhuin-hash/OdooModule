"""End-to-end tests for the public controllers: HttpCase drives real
HTTP requests through the running server as an anonymous visitor, which
is the only way to prove auth='public' + sudo() + the QWeb templates
actually compose into working pages (a TransactionCase can't catch a
template rendering error or a broken route).
"""
import re

from odoo import Command
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestGigPublicPages(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        violin = cls.env['gig.instrument'].create(
            {'name': 'Test Fixture Public Violin'})
        cls.section = cls.env['gig.section'].create({
            'name': 'Test Fixture Public Strings',
            'instrument_line_ids': [
                Command.create({'instrument_id': violin.id, 'quantity': 3}),
            ],
        })
        group = cls.env['gig.section.group'].create(
            {'name': 'Test Fixture Public Orchestra'})
        cls.env['gig.section.group.line'].create({
            'group_id': group.id,
            'section_id': cls.section.id,
        })
        cls.project = cls.env['gig.project'].create({
            'name': 'Public Pages Tour',
            'section_group_id': group.id,
        })
        cls.rehearsal = cls.env['gig.event'].create({
            'project_id': cls.project.id,
            'event_type': 'rehearsal',
            'event_date': '2026-10-01',
            'start_time': 19.0,
            'end_time': 21.0,
        })
        cls.block_both = cls.env['gig.page.block'].create({
            'project_id': cls.project.id,
            'title': 'Public Shared Block',
            'content': '<p>Bring your own stand.</p>',
            'on_registration': True,
            'on_callsheet': True,
        })
        cls.block_callsheet_only = cls.env['gig.page.block'].create({
            'project_id': cls.project.id,
            'title': 'Callsheet Only Block',
            'content': '<p>Dress code: black.</p>',
            'on_registration': False,
            'on_callsheet': True,
        })

    def test_registration_page_renders(self):
        """The public page must serve anonymously and show the project
        info, the section dropdown, and the registration-page blocks -
        but NOT the callsheet-only block (that's the per-page filtering
        the two booleans exist for)."""
        response = self.url_open('/gig/%d/register' % self.project.id)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Public Pages Tour', response.text)
        self.assertIn('Test Fixture Public Strings', response.text)
        self.assertIn('Public Shared Block', response.text)
        self.assertNotIn('Callsheet Only Block', response.text)

    def test_callsheet_page_renders(self):
        """The callsheet shows both its own blocks and the shared one -
        one record serving two pages."""
        response = self.url_open('/gig/%d/callsheet' % self.project.id)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Public Pages Tour', response.text)
        self.assertIn('Public Shared Block', response.text)
        self.assertIn('Callsheet Only Block', response.text)

    def test_unknown_project_404s(self):
        response = self.url_open('/gig/999999999/register')
        self.assertEqual(response.status_code, 404)

    def test_submit_creates_pending_registration(self):
        """Full anonymous submission round-trip: fetch the form (for
        the CSRF token, exactly like a browser), POST it, and check the
        staging record - pending, unlinked, with the RSVP line."""
        page = self.url_open('/gig/%d/register' % self.project.id)
        token_match = re.search(
            r'name="csrf_token" value="([^"]+)"', page.text)
        self.assertTrue(token_match, "CSRF token not found in the form")
        response = self.url_open(
            '/gig/%d/register/submit' % self.project.id,
            data={
                'csrf_token': token_match.group(1),
                'name': 'Anonymous Applicant',
                'email': 'applicant@example.com',
                'phone': '0470 99 88 77',
                'section_id': str(self.section.id),
                'attendance_%d' % self.rehearsal.id: 'present',
            },
        )
        self.assertEqual(response.status_code, 200)
        registration = self.env['gig.registration'].search([
            ('project_id', '=', self.project.id),
            ('email', '=', 'applicant@example.com'),
        ])
        self.assertEqual(len(registration), 1)
        self.assertEqual(registration.state, 'pending')
        self.assertFalse(registration.partner_id)
        self.assertEqual(registration.section_id, self.section)
        self.assertEqual(registration.attendance_line_ids.event_id, self.rehearsal)
        self.assertEqual(registration.attendance_line_ids.status, 'present')
