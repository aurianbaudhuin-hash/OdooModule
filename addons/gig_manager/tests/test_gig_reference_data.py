"""Tests for gig.instrument, gig.piece.type and gig.movement.

These three models are deliberately near-identical: each is just a
required, unique `name` field with no other business logic. Bundling
them into one file (three small TestCase classes) avoids three
almost-duplicate files whose only difference is which model they
point at - the interesting thing being verified (the uniqueness
constraint) is the same shape for all three.
"""
import psycopg2

from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestGigInstrument(TransactionCase):

    def test_create_instrument(self):
        """A plain instrument with a unique name should simply be creatable."""
        instrument = self.env['gig.instrument'].create({'name': 'Test Fixture Violin'})
        self.assertTrue(instrument.id)

    def test_duplicate_name_raises(self):
        """The _sql_constraints unique('name') must block a second row
        with the same name.

        This is enforced by Postgres, not Python, so the violation only
        surfaces once the INSERT actually reaches the database - hence
        the explicit flush_all() as the last statement in the block below.
        Once Postgres raises, the whole transaction is left in an
        "aborted" state, so any further SQL in this test method (even an
        unrelated read) would fail with InFailedSqlTransaction unless we
        roll back to a savepoint first; cr.savepoint() does exactly that
        on its __exit__. mute_logger silences the (expected, harmless)
        ERROR-level log Odoo prints for the constraint violation, so the
        test output isn't cluttered with what looks like a real crash.

        Fixture names in this file are prefixed "Test Fixture" rather
        than using plain instrument/piece-type/movement names: this suite
        runs against odoo_db, the same database used for real day-to-day
        work (per this repo's documented test command), not a disposable
        throwaway database - a plain name like "Violin" could collide
        with a real record a user already created through the UI.
        """
        self.env['gig.instrument'].create({'name': 'Test Fixture Violin'})
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self.env['gig.instrument'].create({'name': 'Test Fixture Violin'})
            self.env.flush_all()


@tagged('post_install', '-at_install')
class TestGigPieceType(TransactionCase):

    def test_create_piece_type(self):
        """A plain piece type with a unique name should simply be creatable."""
        piece_type = self.env['gig.piece.type'].create({'name': 'Test Fixture Symphony'})
        self.assertTrue(piece_type.id)

    def test_duplicate_name_raises(self):
        """Same uniqueness guarantee as gig.instrument, see that test's
        docstring for why the savepoint/flush/mute_logger combo is needed."""
        self.env['gig.piece.type'].create({'name': 'Test Fixture Symphony'})
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self.env['gig.piece.type'].create({'name': 'Test Fixture Symphony'})
            self.env.flush_all()


@tagged('post_install', '-at_install')
class TestGigMovement(TransactionCase):

    def test_create_movement(self):
        """A plain artistic movement with a unique name should simply be creatable."""
        movement = self.env['gig.movement'].create({'name': 'Test Fixture Baroque'})
        self.assertTrue(movement.id)

    def test_duplicate_name_raises(self):
        """Same uniqueness guarantee as gig.instrument, see that test's
        docstring for why the savepoint/flush/mute_logger combo is needed."""
        self.env['gig.movement'].create({'name': 'Test Fixture Baroque'})
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self.env['gig.movement'].create({'name': 'Test Fixture Baroque'})
            self.env.flush_all()
