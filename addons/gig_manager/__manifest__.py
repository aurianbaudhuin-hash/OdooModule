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
    # 'mail' is already pulled in transitively by 'contacts', but this
    # module now uses mail.template directly - depending on it explicitly
    # keeps the manifest honest about what the code imports.
    'depends': ['base', 'contacts', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/gig_mail_templates.xml',
        'views/gig_instrument_views.xml',
        'views/gig_piece_type_views.xml',
        'views/gig_movement_views.xml',
        'views/gig_composer_views.xml',
        'views/gig_piece_views.xml',
        'views/gig_project_views.xml',
        'views/gig_event_views.xml',
        'views/gig_attendance_views.xml',
        'views/gig_section_views.xml',
        'views/gig_section_group_views.xml',
        'views/gig_registration_views.xml',
        'views/gig_registration_resolve_views.xml',
        'views/gig_mail_template_views.xml',
        'views/gig_public_templates.xml',
        'views/res_partner_views.xml',
        'views/gig_menus.xml',
    ],
    'application': True,
    'installable': True,
}