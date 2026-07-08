{
    'name': 'Gig Manager',
    'version': '1.0',
    'summary': "Manage tours and their individual gigs",
    'description': "Track touring projects, their gigs, venues and setlists.",
    'author': 'Aurian Baudhuin',
    'category': 'Services/Other',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/gig_project_views.xml',
        'views/gig_event_views.xml',
    ],
    'installable': True,
    'application': True,
}