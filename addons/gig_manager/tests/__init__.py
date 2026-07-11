# Import order roughly mirrors the models' dependency order (reference
# data first, then the models that point at it, then the junction
# models that tie everything together) - this has no functional effect
# on test discovery/execution, it just makes the list easier to scan.
from . import test_gig_reference_data
from . import test_gig_composer
from . import test_gig_piece
from . import test_gig_partner_instrument
from . import test_gig_event
from . import test_gig_section
from . import test_gig_project
from . import test_gig_project_participant
from . import test_gig_attendance
from . import test_gig_registration
from . import test_gig_public_pages
from . import test_gig_mail
from . import test_res_partner
