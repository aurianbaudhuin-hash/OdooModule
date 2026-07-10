from odoo import models, fields

class GigMovement(models.Model):
    _name = 'gig.movement'
    _description = 'Artistic movement / musical style (Baroque, Romantic, etc.)'
    _order = 'name'
    name = fields.Char(string="Name", required=True)
    _sql_constraints = [
        ('name_unique', 'unique(name)', "This artistic movement already exists.")
        ]