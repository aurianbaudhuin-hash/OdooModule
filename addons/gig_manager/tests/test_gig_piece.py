"""gig.piece: composition year vs composer lifespan (incl. the year-0
quirk, documented not fixed) and display_name.
"""
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGigPiece(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.piece_type = cls.env['gig.piece.type'].create({'name': 'Test Fixture Symphony'})

    def test_composition_year_before_birth_raises(self):
        composer = self.env['gig.composer'].create({
            'full_name': 'Future Composer',
            'birth_date': '1950-01-01',
        })
        with self.assertRaises(ValidationError):
            self.env['gig.piece'].create({
                'title': 'Too Early',
                'composer_id': composer.id,
                'composition_year': 1900,
                'piece_type_id': self.piece_type.id,
            })

    def test_composition_year_after_death_raises(self):
        composer = self.env['gig.composer'].create({
            'full_name': 'Long Dead Composer',
            'death_date': '1800-01-01',
        })
        with self.assertRaises(ValidationError):
            self.env['gig.piece'].create({
                'title': 'Too Late',
                'composer_id': composer.id,
                'composition_year': 1850,
                'piece_type_id': self.piece_type.id,
            })

    def test_valid_composition_year_allowed(self):
        composer = self.env['gig.composer'].create({
            'full_name': 'Well Timed Composer',
            'birth_date': '1800-01-01',
            'death_date': '1870-01-01',
        })
        piece = self.env['gig.piece'].create({
            'title': 'Just Right',
            'composer_id': composer.id,
            'composition_year': 1840,
            'piece_type_id': self.piece_type.id,
        })
        self.assertTrue(piece.id)

    def test_composer_with_no_dates_skips_check(self):
        # no dates on the composer -> nothing to compare against
        composer = self.env['gig.composer'].create({'full_name': 'Mystery Composer'})
        piece = self.env['gig.piece'].create({
            'title': 'Undated Origins',
            'composer_id': composer.id,
            'composition_year': 1750,
            'piece_type_id': self.piece_type.id,
        })
        self.assertTrue(piece.id)

    def test_composition_year_zero_silently_skips_check(self):
        """Known quirk, left as is: the constraint's guard is
        `if not piece.composition_year`, and 0 is falsy, so year 0
        skips the lifespan check entirely. Not worth fixing (0 is never
        a real year) but this test pins it so a change to the guard
        doesn't slip by unnoticed.
        """
        composer = self.env['gig.composer'].create({
            'full_name': 'Guarded Composer',
            'birth_date': '1950-01-01',
        })
        piece = self.env['gig.piece'].create({
            'title': 'Year Zero',
            'composer_id': composer.id,
            'composition_year': 0,
            'piece_type_id': self.piece_type.id,
        })
        self.assertTrue(piece.id)

    def test_display_name_with_composer(self):
        composer = self.env['gig.composer'].create({'full_name': 'Mozart'})
        piece = self.env['gig.piece'].create({
            'title': 'Requiem',
            'composer_id': composer.id,
            'composition_year': 1791,
            'piece_type_id': self.piece_type.id,
        })
        self.assertEqual(piece.display_name, 'Mozart - Requiem')

    def test_display_name_recomputes_after_composer_rename(self):
        # the dotted @api.depends('composer_id.full_name') at work:
        # renaming the composer refreshes the piece's label too
        composer = self.env['gig.composer'].create({'full_name': 'Mozart'})
        piece = self.env['gig.piece'].create({
            'title': 'Requiem',
            'composer_id': composer.id,
            'composition_year': 1791,
            'piece_type_id': self.piece_type.id,
        })
        self.assertEqual(piece.display_name, 'Mozart - Requiem')
        composer.full_name = 'Wolfgang Amadeus Mozart'
        self.assertEqual(piece.display_name, 'Wolfgang Amadeus Mozart - Requiem')
