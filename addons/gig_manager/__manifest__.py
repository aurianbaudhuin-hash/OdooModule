{
    'name': "Gig Manager",
    'version': '1.0',
    'summary': "Plan concerts and rehearsals for bands and orchestras",
    'description': """
Gig Manager
===========
Manage tours, concerts and rehearsals for bands and orchestras: plan events,
build a programme of musical pieces, and track which contact plays which
instrument, at which level, on which project.
""",
    'category': 'Productivity',
    'author': "Aurian",
    'license': 'LGPL-3',
    'depends': ['base', 'contacts'],
    'data': [
        'security/ir.model.access.csv',
        'views/gig_instrument_views.xml',
        'views/gig_piece_type_views.xml',
        'views/gig_movement_views.xml',
        'views/gig_composer_views.xml',
        'views/gig_piece_views.xml',
        'views/gig_project_views.xml',
        'views/gig_event_views.xml',
        'views/res_partner_views.xml',
        'views/gig_menus.xml',
    ],
    'application': True,
    'installable': True,
}