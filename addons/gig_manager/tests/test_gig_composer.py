"""gig.composer: date ordering constraint, display_name (incl. the
@api.depends regression), restrict-delete when pieces exist.
"""
import psycopg2

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestGigComposer(TransactionCase):

    def test_death_before_birth_raises(self):
        with self.assertRaises(ValidationError):
            self.env['gig.composer'].create({
                'full_name': 'Impossible Composer',
                'birth_date': '1950-01-01',
                'death_date': '1900-01-01',
            })

    def test_equal_birth_and_death_date_allowed(self):
        # constraint is strict <, same-day birth and death passes -
        # pinning the boundary so it doesn't change by accident
        composer = self.env['gig.composer'].create({
            'full_name': 'Same Day Composer',
            'birth_date': '1900-01-01',
            'death_date': '1900-01-01',
        })
        self.assertTrue(composer.id)

    def test_only_one_date_set_is_allowed(self):
        # living composer / unknown birth date: nothing to compare,
        # nothing to block
        composer = self.env['gig.composer'].create({
            'full_name': 'Living Composer',
            'birth_date': '1990-01-01',
        })
        self.assertTrue(composer.id)

    def test_display_name_at_creation(self):
        composer = self.env['gig.composer'].create({'full_name': 'Johann Sebastian Bach'})
        self.assertEqual(composer.display_name, 'Johann Sebastian Bach')

    def test_display_name_recomputes_after_write(self):
        """Regression: _compute_display_name used to lack
        @api.depends('full_name'), so a rename left the old label in
        cache for the rest of the transaction. This read-after-write
        must see the new name.
        """
        composer = self.env['gig.composer'].create({'full_name': 'Bach'})
        self.assertEqual(composer.display_name, 'Bach')
        composer.full_name = 'J.S. Bach'
        self.assertEqual(composer.display_name, 'J.S. Bach')

    def test_cannot_delete_composer_with_pieces(self):
        # restrict on gig.piece.composer_id - a composer with pieces
        # can't be deleted. FK-level, so the usual savepoint dance.
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
