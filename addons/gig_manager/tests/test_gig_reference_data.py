"""gig.instrument / gig.piece.type / gig.movement in one file: they're
all just a unique name field, three separate files would be copy-paste.
"""
import psycopg2

from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestGigInstrument(TransactionCase):

    def test_create_instrument(self):
        instrument = self.env['gig.instrument'].create({'name': 'Test Fixture Violin'})
        self.assertTrue(instrument.id)

    def test_duplicate_name_raises(self):
        """unique(name) is a Postgres constraint, so it only fires at
        flush - hence the explicit flush_all(). The savepoint matters:
        after the IntegrityError the transaction is aborted and any
        later SQL in the test would die with InFailedSqlTransaction.
        mute_logger just hides the expected ERROR line.

        (Names are "Test Fixture ..." everywhere in this suite because
        it runs on odoo_db, the same DB I use manually - a plain
        "Violin" could collide with a real record.)
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
        piece_type = self.env['gig.piece.type'].create({'name': 'Test Fixture Symphony'})
        self.assertTrue(piece_type.id)

    def test_duplicate_name_raises(self):
        # same as the instrument test, see there for the savepoint story
        self.env['gig.piece.type'].create({'name': 'Test Fixture Symphony'})
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self.env['gig.piece.type'].create({'name': 'Test Fixture Symphony'})
            self.env.flush_all()


@tagged('post_install', '-at_install')
class TestGigMovement(TransactionCase):

    def test_create_movement(self):
        movement = self.env['gig.movement'].create({'name': 'Test Fixture Baroque'})
        self.assertTrue(movement.id)

    def test_duplicate_name_raises(self):
        # same as the instrument test
        self.env['gig.movement'].create({'name': 'Test Fixture Baroque'})
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self.env['gig.movement'].create({'name': 'Test Fixture Baroque'})
            self.env.flush_all()
