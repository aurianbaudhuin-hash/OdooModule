# gig_manager
This project is a custom **Odoo 18** module for managing music projects: tours, concerts and rehearsals for bands and orchestras. An organizer creates a project, plans its events, builds a programme of musical pieces, defines the orchestral layout (sections and headcounts), and manages the musicians: public registrations, contact deduplication, attendance tracking and email notifications. It was built to demonstrate knowledge of the Odoo framework, from the ORM and business logic down to public website pages and the mail system.

## Features
- **Projects**: tours or concert series, with computed start/end dates based on the first rehearsal and last concert.
- **Events**: concerts and rehearsals with date, time slot and location. Rehearsals cannot carry a name (enforced at model level, not just in the view).
- **Programme**: musical pieces with composer, type and composition year (validated against the composer's lifespan).
- **Sections and section groups**: reusable ensemble sections ("First violin" = 12x violin, "Flute & Piccolo" = 2x flute + 1x piccolo) organized in ordered, drag-and-drop section groups. Every project is tied to exactly one section group.
- **Participants**: every musician on a project is registered in a section of the project's layout.
- **Attendance**: per-event RSVP status (present / absent / uncertain) for every participant, auto-created when a musician joins a project.
- **Public registration page**: anyone can register to a project through a public two-tab page (project info + registration form), with a warning popup when the chosen section is already full.
- **Contact resolution**: before accepting a registration, the organizer links it to an existing contact (duplicates found by email, phone in any format, or name) with field-by-field conflict resolution, or creates a new contact from the form data.
- **Callsheets**: public static pages with all the practical information for confirmed participants.
- **Custom content blocks**: the organizer can add rich HTML blocks (styled text, images, embedded maps) to the registration page and/or the callsheet. A block can be shared by both pages and edited in one place.
- **Emails**: confirmation and refusal emails on registration decisions, plus a collective "callsheet updated" notification, all based on editable `mail.template` records.
- **Extended contacts**: each contact lists the instruments they play and their skill level.
- Full test suite (94 tests): constraints, computed fields, workflows, wizard, public controllers.

## Project structure
````
.
├── README.md
├── docker-compose.yml
└── addons
    └── gig_manager
        ├── __init__.py
        ├── __manifest__.py
        ├── controllers      # public routes (registration page, callsheet)
        ├── data             # mail templates
        ├── models           # one file per model
        ├── security         # access rights (ir.model.access.csv)
        ├── tests            # full test suite
        ├── views            # backend views, menus, public QWeb templates
        └── wizard           # contact resolution wizard
````

## Technologies
- Python 3
- Odoo 18.0
- PostgreSQL 15
- Docker Compose (two services: `odoo` and `db`)
- QWeb templates for the public pages
- Odoo mail framework (`mail.template`) for the notifications

## How to run
Start the stack:
```bash
docker compose up -d
```
Install the module (first time only):
```bash
docker compose run --rm odoo odoo -d odoo_db -i gig_manager --stop-after-init
```
Update after a code change:
```bash
docker compose run --rm odoo odoo -d odoo_db -u gig_manager --stop-after-init
docker compose restart odoo
```
Run the test suite:
```bash
docker compose run --rm odoo odoo -d odoo_db -u gig_manager --test-tags /gig_manager --stop-after-init
```
The backend is available at `http://localhost:8069`. The public pages of a project are at `/gig/<project_id>/register` and `/gig/<project_id>/callsheet`.

## How it works
The intended workflow:
1) The organizer defines the reference data: instruments, sections, and a section group describing the ensemble layout.
2) They create a project, plan its rehearsals and concerts, and build the programme.
3) Musicians register through the public page: name, contact info, the section they want to play in, and their availability for the rehearsals.
4) The organizer reviews each registration: the module searches the contact database for possible matches (same email, same phone in any format, similar name) and lets them either link the registration to an existing contact (choosing field by field which value to keep in case of conflict) or create a new contact from it.
5) On acceptance, the musician becomes a participant, their attendance rows are created and filled with the availability they declared, and a confirmation email with the callsheet link is sent. On refusal, a refusal email is sent.
6) Participants keep up to date through the callsheet page, and the organizer can notify all of them at once when it changes.

## Possible improvements
Since this is a demo aimed at demonstrating knowledge of the Odoo framework, lots of features can be added or improved:
- Automated rehearsal reminder emails (`ir.cron`)
- Ordering the pieces within a project's programme
- Record rules (`ir.rule`) for finer-grained access control
- Demo data for a one-command working example
- Portal access so musicians can update their own attendance
- Multi-company support
- Translations (the module is English-only for now)
- ...
