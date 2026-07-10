"""Tests for gig.partner.instrument: the unique(partner_id, instrument_id)
constraint, and the deliberate ondelete asymmetry between partner_id
(cascade) and instrument_id (restrict).
"""
import psycopg2

from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestGigPartnerInstrument(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Alice Musician'})
        cls.instrument = cls.env['gig.instrument'].create({'name': 'Test Fixture Cello'})

    def test_duplicate_partner_instrument_raises(self):
        """_sql_constraints unique(partner_id, instrument_id): a contact
        should have at most one skill-level entry per instrument - the
        model's own docstring/error message says to edit the existing
        line instead of creating a second one, so this must be enforced
        at the DB level, not just left to UI discipline."""
        self.env['gig.partner.instrument'].create({
            'partner_id': self.partner.id,
            'instrument_id': self.instrument.id,
            'level': 'amateur_medium',
        })
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            self.env['gig.partner.instrument'].create({
                'partner_id': self.partner.id,
                'instrument_id': self.instrument.id,
                'level': 'professional',
            })
            self.env.flush_all()

    def test_deleting_partner_cascades_to_instrument_line(self):
        """partner_id uses ondelete='cascade' (per this codebase's
        convention: 'cascade' for data with no meaning outside its
        parent) - a "which instrument does this contact play" row is
        meaningless once the contact itself is gone, so it should be
        deleted along with the partner rather than orphaned or blocking
        the deletion."""
        partner = self.env['res.partner'].create({'name': 'Temporary Musician'})
        line = self.env['gig.partner.instrument'].create({
            'partner_id': partner.id,
            'instrument_id': self.instrument.id,
            'level': 'student',
        })
        partner.unlink()
        self.assertFalse(line.exists())

    def test_cannot_delete_instrument_in_use(self):
        """instrument_id uses ondelete='restrict' (reference data other
        records depend on) - deleting an instrument that a contact has
        registered as playing must be blocked, since silently cascading
        would erase the contact's skill data along with an unrelated
        housekeeping action on the instrument list."""
        instrument = self.env['gig.instrument'].create({'name': 'Test Fixture Oboe'})
        self.env['gig.partner.instrument'].create({
            'partner_id': self.partner.id,
            'instrument_id': instrument.id,
            'level': 'high_level_professional',
        })
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), \
                self.cr.savepoint():
            instrument.unlink()
            self.env.flush_all()
