from odoo import http
from odoo.http import request


class GigWebsiteController(http.Controller):
    """Public pages: registration (info + form) and callsheet.

    Everything runs as the public user and reads data via sudo() - the
    ACLs grant nothing outside base.group_user, so these routes are the
    only public surface and they expose exactly what the templates
    render. Templates are standalone QWeb on purpose: no website module
    dependency, the organizer writes custom content as gig.page.block
    records in the backend instead of a frontend page builder.
    """

    def _get_project(self, project_id):
        project = request.env['gig.project'].sudo().browse(project_id)
        return project if project.exists() else None

    def _common_page_values(self, project):
        # both pages show the programme and the calendar; 
        # custom blocks are filtered per page by each route
        return {
            'project': project,
            'pieces': project.piece_ids,
            # sorted() here, not an _order change - chronology is what
            # a visitor expects, backend lists are another story
            'events': project.gig_ids.sorted(
                key=lambda e: (e.event_date, e.start_time)
            ),
        }

    @http.route('/gig/<int:project_id>/register', type='http',
                auth='public', methods=['GET'], sitemap=False)
    def registration_page(self, project_id, submitted=False, **kwargs):
        project = self._get_project(project_id)
        if not project:
            return request.not_found()
        values = self._common_page_values(project)
        values.update({
            'blocks': project.page_block_ids.filtered('on_registration'),
            'rehearsals': project.gig_ids.filtered(
                lambda e: e.event_type == 'rehearsal'
            ).sorted(key=lambda e: (e.event_date, e.start_time)),
            'section_fill': project._get_section_fill(),
            # POST/redirect/GET: the submit route redirects back here
            # with ?submitted=1, so refreshing the thank-you state
            # can't resubmit the form
            'submitted': bool(submitted),
        })
        return request.render('gig_manager.page_registration', values)

    @http.route('/gig/<int:project_id>/register/submit', type='http',
                auth='public', methods=['POST'])
    def registration_submit(self, project_id, **post):
        project = self._get_project(project_id)
        if not project:
            return request.not_found()
        name = (post.get('name') or '').strip()
        email = (post.get('email') or '').strip()
        try:
            section_id = int(post.get('section_id') or 0)
        except ValueError:
            section_id = 0
        sections = project.section_group_id.line_ids.section_id
        # the form marks these required, but hand-crafted POSTs won't
        # care - validate again here (and the section check keeps
        # garbage ids away from the model constraint)
        if not name or not email or section_id not in sections.ids:
            return request.redirect('/gig/%d/register' % project.id)
        attendance_commands = []
        for event in project.gig_ids.filtered(lambda e: e.event_type == 'rehearsal'):
            status = post.get('attendance_%d' % event.id)
            if status in ('present', 'absent', 'maybe'):
                attendance_commands.append((0, 0, {
                    'event_id': event.id,
                    'status': status,
                }))
        request.env['gig.registration'].sudo().create({
            'project_id': project.id,
            'name': name,
            'email': email,
            'phone': (post.get('phone') or '').strip(),
            'section_id': section_id,
            'attendance_line_ids': attendance_commands,
        })
        return request.redirect('/gig/%d/register?submitted=1' % project.id)

    @http.route('/gig/<int:project_id>/callsheet', type='http',
                auth='public', methods=['GET'], sitemap=False)
    def callsheet_page(self, project_id, **kwargs):
        project = self._get_project(project_id)
        if not project:
            return request.not_found()
        values = self._common_page_values(project)
        values.update({
            'blocks': project.page_block_ids.filtered('on_callsheet'),
            # participants grouped by section, in the group's drag
            # order - the one place that ordering shows outside the
            # backend
            'sections_with_participants': [
                (line.section_id, project.participant_ids.filtered(
                    lambda p: p.section_id == line.section_id))
                for line in project.section_group_id.line_ids
            ],
        })
        return request.render('gig_manager.page_callsheet', values)
