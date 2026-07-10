from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGigPiece(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Shared across every test in this class: read-only fixtures like
        # this are safe to build once in setUpClass (each test still runs
        # in its own rolled-back sub-transaction), which is faster than
        # re-creating the same piece_type row for every single test.
        # Prefixed to avoid colliding with a real "Symphony" piece type a
        # user may have already created through the UI - this suite runs
        # against odoo_db, the same database used for real work.
        cls.piece_type = cls.env['gig.piece.type'].create({'name': 'Test Fixture Symphony'})

    def test_composition_year_before_birth_raises(self):
        """_check_composition_year must reject a year earlier than the
        composer's birth_date.year - a composer cannot have written
        anything before they existed."""
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
        """Symmetric case: a year after the composer's death_date.year
        must also be rejected."""
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
        """A year that falls within the composer's lifespan must be accepted."""
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
        """When the composer's birth/death dates are both unknown, the
        constraint has nothing to compare against and must not block
        creation - _check_composition_year explicitly continues past a
        composer with no birth_date/death_date set."""
        composer = self.env['gig.composer'].create({'full_name': 'Mystery Composer'})
        piece = self.env['gig.piece'].create({
            'title': 'Undated Origins',
            'composer_id': composer.id,
            'composition_year': 1750,
            'piece_type_id': self.piece_type.id,
        })
        self.assertTrue(piece.id)

    def test_composition_year_zero_silently_skips_check(self):
        """Pins a real quirk of the current implementation rather than
        hiding it: _check_composition_year's guard is
        `if not piece.composition_year or not piece.composer_id: continue`,
        and 0 is falsy in Python. So composition_year=0 bypasses the
        lifespan check entirely, even for a composer whose lifespan would
        otherwise clearly rule it out. This isn't being "fixed" here
        (year 0 isn't a realistic composition year, so the practical
        impact is negligible) - this test just documents the current
        behaviour so a future change to the guard doesn't silently alter it
        without a test noticing.
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
        """display_name should render as "Composer - Title" when a
        composer is set, per this codebase's display_name convention."""
        composer = self.env['gig.composer'].create({'full_name': 'Mozart'})
        piece = self.env['gig.piece'].create({
            'title': 'Requiem',
            'composer_id': composer.id,
            'composition_year': 1791,
            'piece_type_id': self.piece_type.id,
        })
        self.assertEqual(piece.display_name, 'Mozart - Requiem')

    def test_display_name_recomputes_after_composer_rename(self):
        """Unlike gig.composer/gig.event's display_name (which were
        missing @api.depends - see their own tests), gig.piece's
        _compute_display_name already correctly declares
        @api.depends('title', 'composer_id.full_name'). This test is the
        positive contrast case: renaming the composer must be reflected
        in the piece's display_name within the same transaction, with no
        extra work needed, because the dependency is already declared.
        """
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
