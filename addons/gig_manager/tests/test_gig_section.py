"""Tests for gig.section / gig.section.instrument / gig.section.group /
gig.section.group.line: the uniqueness constraints at every level
(section and group names globally, instrument per section, section per
group), the CHECK(quantity > 0) constraint, the
at-least-one-instrument-line Python constraint, section reuse across
groups, the sequence-based ordering of a group's lines, the
musician_count computes, the cascade/restrict split around the
through-model (deleting a group kills its lines but never the shared
sections), and the 'restrict' protections (instrument used by a
section, section used by a group, group used by a project).
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
        # "Test Fixture " prefix on anything with a uniqueness
        # constraint (instrument, section and group names here): this
        # suite runs against the same odoo_db used for real work, so
        # fixtures must not collide with records a user created through
        # the UI.
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
        """_sql_constraints unique(name) on gig.section.group - same
        reference-data convention as gig.instrument & co.: two ensemble
        layouts with the same name would be indistinguishable in the
        required dropdown on gig.project."""
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self.env['gig.section.group'].create(
                {'name': 'Test Fixture Symphony Orchestra'})
            self.env.flush_all()

    def test_duplicate_section_name_raises(self):
        """_sql_constraints unique(name) on gig.section: sections are
        shared reference data (reused across groups), so uniqueness is
        global - two 'First Violin' sections would be indistinguishable
        in every dropdown that offers them."""
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self._create_section('Test Fixture First Violin',
                                 [{'instrument_id': self.violin.id, 'quantity': 6}])
            self.env.flush_all()

    def test_section_reusable_across_groups(self):
        """The whole reason group<->section goes through a line model:
        one shared section ('First violin = 12 players') can appear in
        several ensemble layouts, each ordering it independently -
        instead of every group having to re-create its own copy."""
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
        """_sql_constraints unique(group_id, section_id) on the line
        model: the same section twice in one group is an ambiguous
        duplicate and would double-count its headcount."""
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self.env['gig.section.group.line'].create({
                'group_id': self.group.id,
                'section_id': self.section.id,
            })
            self.env.flush_all()

    def test_duplicate_instrument_line_raises(self):
        """_sql_constraints unique(section_id, instrument_id): splitting
        one instrument's headcount across two lines in the same section
        is ambiguous - the error message tells the user to edit the
        existing line's headcount instead."""
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
        """CHECK(quantity > 0): a zero-headcount line is nonsense data.
        This is a plain single-field invariant, so it lives in
        _sql_constraints as a DB CHECK - hence the IntegrityError (not
        ValidationError) expected here, same as the unique constraints."""
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
        """@api.constrains on instrument_line_ids: a section is defined
        as *one or more* instruments with a headcount, so an empty one
        is invalid data. This needs Python (is the One2many empty?), not
        SQL, hence ValidationError rather than IntegrityError."""
        with self.assertRaises(ValidationError):
            self.env['gig.section'].create({
                'name': 'Test Fixture Empty Section',
            })

    def test_musician_count_sums_line_quantities(self):
        """gig.section.musician_count is the sum of its lines'
        quantities, and gig.section.group.musician_count aggregates the
        counts of the sections its lines point at - the '2x flute +
        1x piccolo'-style mixed section from the spec is exercised
        here."""
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
        """gig.section.group.line._order = 'sequence, id': the group's
        line_ids One2many must come back in drag-handle order, not
        creation order - so this test creates the lines in the *reverse*
        of their intended sequence to prove the ordering is really
        driven by the sequence field."""
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
        # Within a single transaction the One2many cache just appends
        # records in creation order - the comodel's _order is only
        # applied when the field is actually (re)read from the DB.
        # Invalidating first mimics what every new web request does,
        # which is the situation this ordering exists for.
        group.invalidate_recordset(['line_ids'])
        self.assertEqual(group.line_ids.ids, [first.id, last.id])

    def test_deleting_group_cascades_to_lines_but_not_sections(self):
        """The cascade/restrict split around the through-model: a line
        (a *position* entry) has no meaning without its group, so it
        dies with it - but the section it points at is shared reference
        data that other groups may still use, so it must survive."""
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
        """gig.section.group.line.section_id uses ondelete='restrict':
        deleting a section that some group's layout still includes must
        be blocked, not silently rewrite that group's composition."""
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self.section.unlink()
            self.env.flush_all()

    def test_cannot_delete_instrument_used_in_section(self):
        """instrument_id uses ondelete='restrict' - deleting an
        instrument that a section's makeup depends on must be blocked,
        exactly like gig.partner.instrument protects it."""
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self.violin.unlink()
            self.env.flush_all()

    def test_cannot_delete_group_used_by_project(self):
        """gig.project.section_group_id uses ondelete='restrict': the
        group is shared reference data (like composer_id on gig.piece),
        so deleting a layout that a live project relies on must be
        blocked rather than cascading into the project or nulling a
        required field."""
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
        """Every project must declare exactly one ensemble layout.

        Asserted on the field definition rather than by creating a
        project without a group and expecting a NOT NULL violation: this
        suite runs against odoo_db, the same database used for real
        work, and if any project predating this field still has a NULL
        section_group_id, Odoo will have skipped applying the NOT NULL
        column constraint (it logs an error and moves on) - making the
        DB-level assertion flaky on exactly the databases that matter.
        The ORM-level required=True checked here is what actually gates
        every create/write from the UI and from code either way."""
        self.assertTrue(self.env['gig.project']._fields['section_group_id'].required)
