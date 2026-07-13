"""Sections, section groups and their through-model: uniqueness at
every level, the quantity CHECK, the at-least-one-instrument rule,
reuse across groups, line ordering, the counts, and the
cascade/restrict split (deleting a group kills its lines, never the
shared sections).
"""
import psycopg2

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestGigSection(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.violin = cls.env['gig.instrument'].create(
            {'name': 'Test Fixture Section Violin'})
        cls.flute = cls.env['gig.instrument'].create(
            {'name': 'Test Fixture Section Flute'})
        cls.section = cls.env['gig.section'].create({
            'name': 'Test Fixture First Violin',
            'instrument_line_ids': [
                Command.create({'instrument_id': cls.violin.id, 'quantity': 12}),
            ],
        })
        cls.group = cls.env['gig.section.group'].create(
            {'name': 'Test Fixture Symphony Orchestra'})
        cls.line = cls.env['gig.section.group.line'].create({
            'group_id': cls.group.id,
            'section_id': cls.section.id,
        })

    def _create_section(self, name, lines):
        return self.env['gig.section'].create({
            'name': name,
            'instrument_line_ids': [Command.create(vals) for vals in lines],
        })

    def test_duplicate_group_name_raises(self):
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self.env['gig.section.group'].create(
                {'name': 'Test Fixture Symphony Orchestra'})
            self.env.flush_all()

    def test_duplicate_section_name_raises(self):
        # global uniqueness - sections are shared reference data now
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self._create_section('Test Fixture First Violin',
                                 [{'instrument_id': self.violin.id, 'quantity': 6}])
            self.env.flush_all()

    def test_section_reusable_across_groups(self):
        # the whole reason the group<->section link is a line model:
        # one section, several layouts
        other_group = self.env['gig.section.group'].create(
            {'name': 'Test Fixture Opera Pit'})
        line = self.env['gig.section.group.line'].create({
            'group_id': other_group.id,
            'section_id': self.section.id,
        })
        self.assertTrue(line.exists())
        self.assertEqual(
            self.section.group_line_ids.group_id,
            self.group | other_group,
        )

    def test_duplicate_section_in_same_group_raises(self):
        # same section twice in one group = double-counted headcount
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self.env['gig.section.group.line'].create({
                'group_id': self.group.id,
                'section_id': self.section.id,
            })
            self.env.flush_all()

    def test_duplicate_instrument_line_raises(self):
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self.env['gig.section.instrument'].create({
                'section_id': self.section.id,
                'instrument_id': self.violin.id,
                'quantity': 3,
            })
            self.env.flush_all()

    def test_zero_quantity_raises(self):
        # CHECK(quantity > 0) is a DB constraint, hence IntegrityError
        # and not ValidationError
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self.env['gig.section.instrument'].create({
                'section_id': self.section.id,
                'instrument_id': self.flute.id,
                'quantity': 0,
            })
            self.env.flush_all()

    def test_section_without_instrument_lines_raises(self):
        # python constraint (is the O2M empty?), can't be SQL
        with self.assertRaises(ValidationError):
            self.env['gig.section'].create({
                'name': 'Test Fixture Empty Section',
            })

    def test_musician_count_sums_line_quantities(self):
        # the "2x flute + 1x piccolo" example from the spec
        piccolo = self.env['gig.instrument'].create(
            {'name': 'Test Fixture Piccolo'})
        mixed = self._create_section('Test Fixture Flute And Piccolo', [
            {'instrument_id': self.flute.id, 'quantity': 2},
            {'instrument_id': piccolo.id, 'quantity': 1},
        ])
        self.assertEqual(mixed.musician_count, 3)
        self.env['gig.section.group.line'].create({
            'group_id': self.group.id,
            'section_id': mixed.id,
        })
        # 12 (First Violin fixture) + 3 (this section)
        self.assertEqual(self.group.musician_count, 15)

    def test_lines_ordered_by_sequence(self):
        # created in reverse of the intended order, to prove the
        # ordering comes from the sequence field and not creation order
        woodwinds = self._create_section('Test Fixture Woodwinds',
                                         [{'instrument_id': self.flute.id, 'quantity': 4}])
        group = self.env['gig.section.group'].create(
            {'name': 'Test Fixture Ordered Band'})
        last = self.env['gig.section.group.line'].create({
            'group_id': group.id, 'section_id': self.section.id, 'sequence': 30,
        })
        first = self.env['gig.section.group.line'].create({
            'group_id': group.id, 'section_id': woodwinds.id, 'sequence': 10,
        })
        # within one transaction the O2M cache appends in creation
        # order; _order only applies on a fresh read. Invalidate to
        # mimic what a new request does. (Cost me a while.)
        group.invalidate_recordset(['line_ids'])
        self.assertEqual(group.line_ids.ids, [first.id, last.id])

    def test_deleting_group_cascades_to_lines_but_not_sections(self):
        # the cascade/restrict split around the through-model: lines
        # die with the group, the shared section survives
        group = self.env['gig.section.group'].create(
            {'name': 'Test Fixture Short Lived Band'})
        line = self.env['gig.section.group.line'].create({
            'group_id': group.id,
            'section_id': self.section.id,
        })
        group.unlink()
        self.assertFalse(line.exists())
        self.assertTrue(self.section.exists())

    def test_cannot_delete_section_used_in_group(self):
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self.section.unlink()
            self.env.flush_all()

    def test_cannot_delete_instrument_used_in_section(self):
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self.violin.unlink()
            self.env.flush_all()

    def test_cannot_delete_group_used_by_project(self):
        # restrict on gig.project.section_group_id
        self.env['gig.project'].create({
            'name': 'Section Group Restrict Tour',
            'section_group_id': self.group.id,
        })
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self.group.unlink()
            self.env.flush_all()

    def test_project_section_group_is_required(self):
        """Checked on the field definition, not by expecting a NOT NULL
        violation: this suite runs on odoo_db, and if any project
        predating the field still has NULL there, postgres refused the
        NOT NULL and the DB-level assertion would be flaky exactly
        where it matters. The ORM required= is what gates writes
        anyway.
        """
        self.assertTrue(self.env['gig.project']._fields['section_group_id'].required)
