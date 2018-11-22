from __future__ import absolute_import
from functools import wraps
import logging

import datman.scanid
import datman.config
from datman.exceptions import DashboardException

logger = logging.getLogger(__name__)

try:
    import dashboard
    from dashboard import queries
except ImportError:
    dash_found = False
    logger.error("Dashboard not found, proceeding without it.")
else:
    dash_found = True



def dashboard_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not dash_found:
            if 'create' in kwargs.keys() or f.__name__.startswith('add'):
                raise DashboardException("Can't add record. Dashboard not "
                        "installed or configured")
            return None
        return f(*args, **kwargs)
    return decorated_function


def scanid_required(f):
    """
    This decorator checks that the wrapped function's first argument is an
    instance of datman.scanid.Identifier and attempts to convert it if not.

    A DashboardException will be raised if an Identifier isn't found or can't
    be created
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        name = args[0]
        if not isinstance(name, datman.scanid.Identifier):
            try:
                name = datman.scanid.parse(name)
            except datman.scanid.ParseException:
                raise DashboardException("Expected: a valid subject ID or "
                        "an instance of datman.scanid.Identifier. Received: "
                        "{}".format(name))
            args = list(args)
            args[0] = name
        return f(*args, **kwargs)
    return decorated_function


def filename_required(f):
    """
    This decorator checks that the wrapped function has received a datman
    style file name as either a string or as a datman.scanid.Identifier instance
    with kwargs tag, series, and description set.

    A DashboardException will be raised if the expected information is not given
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        name = args[0]
        if not isinstance(name, datman.scanid.Identifier):
            try:
                name, tag, series, descr = datman.scanid.parse_filename(name)
            except:
                try:
                    name = datman.scanid.parse(name)
                except:
                    raise DashboardException("A datman file name was expected. "
                            "Received {} instead.".format(name))
                try:
                    tag = kwargs['tag']
                    series = kwargs['series']
                    descr = kwargs['description']
                except:
                    raise DashboardException("An expected keyword argument "
                            "wasnt found. Please ensure either 'tag', "
                            "'series', and 'description' are set, or a "
                            "datman filename is given as an argument.")
            args = list(args)
            args[0] = name
            kwargs['tag'] = tag
            kwargs['series'] = series
            kwargs['description'] = descr
        elif ('tag' not in kwargs or
                'series' not in kwargs or
                'description' not in kwargs):
            raise DashboardException("An expected option was unset. This "
                    "function requires either a datman ident + 'tag', 'series' "
                    "and 'description' options be set or that a full filename "
                    "is given as a string")
        return f(*args, **kwargs)
    return decorated_function


@dashboard_required
@scanid_required
def get_subject(name, create=False):
    found = queries.find_subjects(name.get_full_subjectid_with_timepoint())
    if len(found) > 1:
        raise DashboardException("Couldnt identify record for {}. {} matching "
            "records found".format(name, len(found)))
    if len(found) == 1:
        return found[0]

    if create:
        return add_subject(name)

    return None


@dashboard_required
@scanid_required
def add_subject(name):
    studies = queries.get_study(name.study, site=name.site)
    if not studies:
        raise DashboardException("ID {} contains invalid study / site "
                "combination".format(name))
    if len(studies) > 1:
        raise DashboardException("Can't identify study for {}. {} matching "
                "records found for that study / site combination".format(name,
                len(studies)))
    study = studies[0].study

    return study.add_timepoint(name)

    # 3. If date convert to datetime object
    # 4. Search DB for sessions where study = current.study and name = current.name
    # 5. If match, take first. If date:
        # 5a. convert db_session's date to datetime
        # 5b. convert date again??? (strftime this time instead of strptime)
        # 5c. If the two arent equal: update the date to the new one
    # 6. If no match + create set add new record, else return None
    # 7. Get checklist comment (if any), if differs from existing - update it
    # Commit and return the session

@dashboard_required
@scanid_required
def get_session(name, create=False):
    session = queries.get_session(name.get_full_subjectid_with_timepoint(),
            _get_session_num(name))

    if not session and create:
        session = add_session(name)

    return session


@dashboard_required
@scanid_required
def add_session(name):
    timepoint = get_subject(name, create=True)
    sess_num = _get_session_num(name)

    if timepoint.is_phantom and sess_num > 1:
        raise DashboardException("ERROR: attempt to add repeat scan session to "
                "phantom {}".format(str(name)))

    return timepoint.add_session(sess_num)


def _get_session_num(datman_id):
    try:
        sess_num = int(datman_id.session)
    except ValueError:
        if datman.scanid.is_phantom(datman_id):
            sess_num = 1
        else:
            raise DashboardException("ID {} contains invalid session "
                    "number".format(str(datman_id)))
    return sess_num


@dashboard_required
@filename_required
def get_scan(name, tag=None, series=None, description=None, create=False):
    scan_name = _get_scan_name(name, tag, series)

    scan = queries.get_scan(scan_name,
            timepoint=name.get_full_subjectid_with_timepoint(),
            session=name.session)

    if len(scan) > 1:
        raise DashboardException("Couldnt identify scan {}. {} matches "
                "found".format(scan_name, len(scan)))
    if len(scan) == 1:
        return scan[0]

    if create:
        return add_scan(name, tag=tag, series=series, description=description)

    return None


@dashboard_required
@filename_required
def add_scan(name, tag=None, series=None, description=None):
    session = get_session(name, create=True)
    studies = queries.get_study(name.study, site=name.site)
    scan_name = _get_scan_name(name, tag, series)

    if len(studies) != 1:
        raise DashboardException("Can't identify study to add scan {} to. {} "
                "matches found.".format(scan_name, len(studies)))
    study = studies[0].study
    allowed_tags = [st.tag for st in study.scantypes]

    if tag not in allowed_tags:
        raise DashboardException("Scan name {} contains tag not configured "
                "for study {}".format(scan_name, study))

    return session.add_scan(scan_name, series, tag, description)

    #### HANDLE LINKS!

    # 1. Validate name scheme

    # 2. Search for scan in DB
    # 3. Raise exception if more than one match found (must be unique name)
    # 4. If not found + create (otherwise return None)
        # 4a. get_session(sess_name, create=create) (reraise if exception)
        # 4b. Try to get scantype from tag
        # 4c. validate that tag belongs in this study
        # 4d. Add to database
    # 5. Get blacklist comment from filesystem, update if differs

def _get_scan_name(ident, tag, series):
    name = "_".join([str(ident), tag, str(series)])
    return name


@dashboard_required
def delete_extra_scans(session, file_names):
    if not dash_found:
        logger.info("No dashboard installed.")
        return None
    # 1. Read into datman ident
    # 2. Get session from database (if there is one)
    # 3. For each scan in file_names, get the database record and add name to db_names
    # 4. Filter out links + spirals (???)
    # 5. 'extra scans' = set in database - set on file system
    # 6. For each item in extra scans, delete it from the database

@dashboard_required
def get_scantype(scantype):
    if not dash_found:
        return None
    # 1. Just query the database for the tag and return?

# @dashboard_required
# def delete_subject(name):
    # 1. Retrieve from database
    # 2. Delete, report if attempting to delete non-existent?
    # 3. Return True if delete, false otherwise

# @dashboard_required
# def is_linked(scan):
    # 1. Return the database att, unless SPRL in which case hard-coded true????

# Not needed anymore? Or need new function to handle links...)
# def get_session_scan_link()
    # 1. Searched DB for match on session and scan name
    # 2. Returned existing, or made new
    # 3. Set is_primary to False (so... this is only called for actual links?)

# @dashboard_required
# def add_redcap():
    # 1. Makes a redcap record
