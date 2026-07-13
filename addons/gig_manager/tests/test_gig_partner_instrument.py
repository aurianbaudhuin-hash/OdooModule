"""gig.partner.instrument: unique (partner, instrument) and the
cascade/restrict asymmetry between the two FKs.
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
        # one skill entry per instrument per contact
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
        # cascade: skill lines go down with their contact
        partner = self.env['res.partner'].create({'name': 'Temporary Musician'})
        line = self.env['gig.partner.instrument'].create({
            'partner_id': partner.id,
            'instrument_id': self.instrument.id,
            'level': 'student',
        })
        partner.unlink()
        self.assertFalse(line.exists())

    def test_cannot_delete_instrument_in_use(self):
        # restrict: deleting an instrument someone plays is blocked
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
