"""Tests for gig.composer: the birth/death date ordering constraint,
display_name (including the recompute-after-write regression test for
the previously-missing @api.depends), and the restrict-delete guarantee
on gig.piece.composer_id.
"""
import psycopg2

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestGigComposer(TransactionCase):

    def test_death_before_birth_raises(self):
        """_check_dates must reject a death_date earlier than birth_date -
        that combination is never physically possible, so it's a pure
        data-entry error worth catching at the model level rather than
        letting bad dates silently sit in the database."""
        with self.assertRaises(ValidationError):
            self.env['gig.composer'].create({
                'full_name': 'Impossible Composer',
                'birth_date': '1950-01-01',
                'death_date': '1900-01-01',
            })

    def test_equal_birth_and_death_date_allowed(self):
        """The constraint is death_date < birth_date, not <=, so a composer
        who (bizarrely) has the same birth and death date on record is not
        blocked - this pins that boundary condition intentionally."""
        composer = self.env['gig.composer'].create({
            'full_name': 'Same Day Composer',
            'birth_date': '1900-01-01',
            'death_date': '1900-01-01',
        })
        self.assertTrue(composer.id)

    def test_only_one_date_set_is_allowed(self):
        """A living composer (or one whose birth date is simply unknown)
        should never be blocked by this constraint: _check_dates only
        compares the two dates when *both* are present."""
        composer = self.env['gig.composer'].create({
            'full_name': 'Living Composer',
            'birth_date': '1990-01-01',
        })
        self.assertTrue(composer.id)

    def test_display_name_at_creation(self):
        """display_name should mirror full_name for a freshly created record."""
        composer = self.env['gig.composer'].create({'full_name': 'Johann Sebastian Bach'})
        self.assertEqual(composer.display_name, 'Johann Sebastian Bach')

    def test_display_name_recomputes_after_write(self):
        """Regression test for the missing @api.depends('full_name') bug
        that used to sit on _compute_display_name.

        display_name is a non-stored computed field, so its cached value
        is only invalidated when a field listed in @api.depends changes.
        Before the fix, renaming a composer left display_name showing the
        old name for the rest of the transaction (e.g. stale breadcrumbs
        or Many2one labels right after a rename, until the next request
        recomputed it from scratch). With the dependency declared, reading
        display_name right after the write must reflect the new name.
        """
        composer = self.env['gig.composer'].create({'full_name': 'Bach'})
        self.assertEqual(composer.display_name, 'Bach')
        composer.full_name = 'J.S. Bach'
        self.assertEqual(composer.display_name, 'J.S. Bach')

    def test_cannot_delete_composer_with_pieces(self):
        """gig.piece.composer_id uses ondelete='restrict' deliberately
        (per this codebase's convention: 'restrict' for reference data
        other records depend on) - a composer who has pieces attached
        must not be deletable, since that would either orphan the piece
        or silently destroy it depending on cascade settings elsewhere.
        This is a DB-level foreign-key restriction, so like the
        uniqueness tests it needs the savepoint/flush/mute_logger combo
        to recover the transaction after the expected IntegrityError.
        """
        composer = self.env['gig.composer'].create({'full_name': 'Beethoven'})
        piece_type = self.env['gig.piece.type'].create({'name': 'Test Fixture Symphony'})
        self.env['gig.piece'].create({
            'title': 'Symphony No. 5',
            'composer_id': composer.id,
            'composition_year': 1808,
            'piece_type_id': piece_type.id,
        })
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            composer.unlink()
            self.env.flush_all()
