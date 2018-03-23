#!/usr/bin/env python
"""
Uploads a scan archive to XNAT

Usage:
    dm_xnat_upload.py [options] <study>
    dm_xnat_upload.py [options] <study> <archive>

Arguments:
    <study>             Study/Project name
    <archive>             Properly named zip file

Options:
    --server URL          XNAT server to connect to, overrides the server defined in the site config file.
    -u --username USER    XNAT username. If specified then the credentials file is ignored and you are prompted for password.
    -v --verbose          Be chatty
    -d --debug            Be very chatty
    -q --quiet            Be quiet
"""

import logging
import sys
from datman.docopt import docopt
import datman.config
import datman.utils
import datman.scanid
import datman.xnat
import datman.exceptions
import os
import getpass
import zipfile
import io
import dicom
import urllib

logger = logging.getLogger(os.path.basename(__file__))

username = None
password = None
server = None
XNAT = None
CFG = None

def main():
    global username
    global server
    global password
    global XNAT
    global CFG

    arguments = docopt(__doc__)
    verbose = arguments['--verbose']
    debug = arguments['--debug']
    quiet = arguments['--quiet']
    study = arguments['<study>']
    server = arguments['--server']
    username = arguments['--username']
    archive = arguments['<archive>']

    # setup logging
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.WARN)
    logger.setLevel(logging.WARN)
    if quiet:
        logger.setLevel(logging.ERROR)
        ch.setLevel(logging.ERROR)
    if verbose:
        logger.setLevel(logging.INFO)
        ch.setLevel(logging.INFO)
    if debug:
        logger.setLevel(logging.DEBUG)
        ch.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s - %(name)s - {study} - '
                                  '%(levelname)s - %(message)s'.format(
                                  study=study))
    ch.setFormatter(formatter)

    logger.addHandler(ch)

    # setup the config object
    logger.info('Loading config')

    CFG = datman.config.config(study=study)

    XNAT = get_xnat(server=server, username=username)

    dicom_dir = CFG.get_path('dicom', study)
    # deal with a single archive specified on the command line,
    # otherwise process all files in dicom_dir
    if archive:
        # check if the specified archive is a valid file
        if os.path.isfile(archive):
            dicom_dir = os.path.dirname(os.path.normpath(archive))
            archives = [os.path.basename(os.path.normpath(archive))]
        elif datman.scanid.is_scanid_with_session(archive):
            # a sessionid could have been provided, lets be nice and handle that
            archives = [datman.utils.splitext(archive)[0] + '.zip']
        else:
            logger.error('Cant find archive:{}'.format(archive))
            return
    else:
        archives = os.listdir(dicom_dir)

    logger.debug('Processing files in:{}'.format(dicom_dir))
    logger.info('Processing {} files'.format(len(archives)))

    for archivefile in archives:
        process_archive(os.path.join(dicom_dir, archivefile))


def process_archive(archivefile):
    """Upload data from a zip archive to the xnat server"""
    scanid = get_scanid(os.path.basename(archivefile))
    if not scanid:
        return

    xnat_session = get_xnat_session(scanid)
    if not xnat_session:
        # failed to get xnat info
        return

    try:
        data_exists, resource_exists = check_files_exist(archivefile, xnat_session)
    except Exception as e:
        logger.error('Failed checking xnat for session: {}'.format(scanid))
        return

    if not data_exists:
        logger.info('Uploading dicoms from: {}'.format(archivefile))
        try:
            upload_dicom_data(archivefile, xnat_session.project, str(scanid))
        except Exception as e:
            logger.error('Failed uploading archive to xnat project: {}'
                         ' for subject: {}. Check Prearchive.'
                         .format(xnat_session.project, str(scanid)))
            logger.info('Upload failed with reason: {}'.format(str(e)))
            return

    if not resource_exists:
        logger.debug('Uploading resource from: {}'.format(archivefile))
        try:
            upload_non_dicom_data(archivefile, xnat_session.project, str(scanid))
        except Exception as e:
            logger.debug('An exception occurred: {}'.format(e))
            pass

    check_duplicate_resources(archivefile, scanid)


def get_xnat_session(ident):
    """
    Get an xnat session from the archive. Returns a session instance holding
    the XNAT json info for this session.

    May raise XnatException if session cant be retrieved
    """
    # get the expected xnat project name from the config filename
    try:
        xnat_project = CFG.get_key(['XNAT_Archive'],
                                   site=ident.site)
    except:
        logger.warning('Study:{}, Site:{}, xnat archive not defined in config'
                       .format(ident.study, ident.site))
        return None
    # check we can get the archive from xnat
    try:
        XNAT.get_project(xnat_project)
    except datman.exceptions.XnatException as e:
        logger.error('Study:{}, Site:{}, xnat archive:{} not found with reason:{}'
                     .format(ident.study, ident.site, xnat_project, e))
        return None
    # check we can get or create the session in xnat
    try:
        xnat_session = XNAT.get_session(xnat_project, str(ident), create=True)
    except datman.exceptions.XnatException as e:
        logger.error('Study:{}, site:{}, archive:{} Failed getting session:{}'
                     ' from xnat with reason:{}'
                     .format(ident.study, ident.site,
                             xnat_project, str(ident), e))
        return None

    return xnat_session


def get_scanid(archivefile):
    """Check we can can a valid scanid from the archive
    Returns a scanid object or False"""
    # currently only look at filename
    # this could look inside the dicoms similar to dm2-link.py
    scanid = archivefile[:-len(datman.utils.get_extension(archivefile))]

    if not datman.scanid.is_scanid_with_session(scanid) and not datman.scanid.is_phantom(scanid):
        logger.error('Invalid scanid:{} from archive:{}'
                       .format(scanid, archivefile))
        return False

    ident = datman.scanid.parse(scanid)
    return(ident)


def resource_data_exists(xnat_session, archive):
    xnat_resources = xnat_session.get_resources(XNAT)
    with zipfile.ZipFile(archive) as zf:
        local_resources = get_resources(zf)

    # paths in xnat are url encoded. Need to fix local paths to match
    local_resources = [urllib.pathname2url(p) for p in local_resources]
    if not set(local_resources).issubset(set(xnat_resources)):
        return False
    return True


def scan_data_exists(xnat_session, local_headers):
    local_scan_uids = [scan.SeriesInstanceUID for scan in local_headers.values()]
    local_experiment_ids = [v.StudyInstanceUID for v in local_headers.values()]

    if len(set(local_experiment_ids)) > 1:
        raise ValueError('More than one experiment UID found - '
                '{}'.format(','.join(local_experiment_ids)))

    if not xnat_session.experiment_UID in local_experiment_ids:
        raise ValueError('Experiment UID doesnt match XNAT')

    if not set(local_scan_uids).issubset(set(xnat_session.scan_UIDs)):
        logger.info('Found UIDs for {} not yet added to xnat'.format(
                xnat_session.name))
        return False

    # XNAT data matches local archive data
    return True


def check_files_exist(archive, xnat_session):
    """Check to see if the dicom files in the local archive have
    been uploaded to xnat
    Returns True if all files exist, otherwise False
    If the session UIDs don't match raises a warning"""
    logger.info('Checking {} contents on xnat'.format(xnat_session.name))
    try:
        local_headers = datman.utils.get_archive_headers(archive)
    except:
        logger.error('Failed getting zip file headers for: {}'.format(archive))
        return False, False

    if not xnat_session.scans:
        return False, False

    try:
        scans_exist = scan_data_exists(xnat_session, local_headers)
    except ValueError as e:
        logger.error("Please check {}: {}".format(archive, e.message))
        # Return true for both to prevent XNAT being modified
        return True, True

    resources_exist = resource_data_exists(xnat_session, archive)

    return scans_exist, resources_exist


def check_duplicate_resources(archive, ident):
    """
    Checks the xnat archive for duplicate resources
    Only  checks if non-dicom files in the archive exist and have duplicates
    Deletes any duplicate copies from xnat
    """
    # process the archive to find out what files have been uploaded
    uploaded_files = []
    with zipfile.ZipFile(archive) as zf:
        uploaded_files = get_resources(zf)

    # Get an updated copy of the xnat_session (otherwise it crashes the first
    # time a subject is uploaded)
    xnat_session = get_xnat_session(ident)
    xnat_resources = xnat_session.get_resources(XNAT)
    # iterate throught the uploded files, finding any duplicates
    # the one to keep should have the same folder structure
    # and be in the MISC folder
    # N.B. default folder is defined in
    for f in uploaded_files:
        fname = os.path.basename(f)
        dups = [resource for resource
                in xnat_resources if resource[1]['name'] == fname]
        orig = [i for i, v in enumerate(dups) if v[1]['URI'] == f]

        #orig = [o for o in orig if dups[o][0][0] == 'MISC']
        if len(orig) > 1:
            logger.warning('Failed to identify unique original resource file:{} '
                           'in session:{}'.format(fname, ident))
            return
        # Delete the original entry from the list
        if not orig:
            logger.warning('Failed to identify original resource file:{} '
                           'in session:{}'.format(fname, ident))
            return
        dups.pop(orig[0])

        # Finally iterate through the duplicates, deleting from xnat
        for d in dups:
            XNAT.delete_resource(xnat_project,
                                 ident.get_full_subjectid_with_timepoint_session(),
                                 ident.get_full_subjectid_with_timepoint_session(),
                                 d[0][1],
                                 d[1]['ID'])


def get_resources(open_zipfile):
    # filter dirs
    files = open_zipfile.namelist()
    files = filter(lambda f: not f.endswith('/'), files)

    # filter files named like dicoms
    files = filter(lambda f: not is_named_like_a_dicom(f), files)

    # filter actual dicoms :D.
    resource_files = []
    for f in files:
        try:
            if not is_dicom(io.BytesIO(open_zipfile.read(f))):
                resource_files.append(f)
        except zipfile.BadZipfile:
            logger.error('Error in zipfile:{}'.format(f))
    return resource_files


def upload_non_dicom_data(archive, xnat_project, scanid):
    with zipfile.ZipFile(archive) as zf:
        resource_files = get_resources(zf)
        logger.info("Uploading {} files of non-dicom data..."
                    .format(len(resource_files)))
        uploaded_files = []
        for item in resource_files:
            # convert to HTTP language
            try:
                contents = zf.read(item)
                if not contents:
                    logger.error("Cannot upload empty resource file {}, "
                            "skipping.".format(item))
                    continue
                # By default files are placed in a MISC subfolder
                # if this is changed it may require changes to
                # check_duplicate_resources()
                XNAT.put_resource(xnat_project,
                                  scanid,
                                  scanid,
                                  item,
                                  contents,
                                  'MISC')
                uploaded_files.append(item)
            except Exception as e:
                logger.error("Failed uploading file {} with error:{}"
                             .format(item, str(e)))
        return uploaded_files


def upload_dicom_data(archive, xnat_project, scanid):
    try:
        ##update for XNAT
        XNAT.put_dicoms(xnat_project, scanid, scanid, archive)
    except Exception as e:
        raise e


def is_named_like_a_dicom(path):
    dcm_exts = ('dcm', 'img')
    return any(map(lambda x: path.lower().endswith(x), dcm_exts))


def is_dicom(fileobj):
    try:
        dicom.read_file(fileobj)
        return True
    except dicom.filereader.InvalidDicomError:
        return False


def get_xnat(server=None, username=None):
    """Create an xnat object,
    this represents a connection to the xnat server as well as functions
    for listing / adding data"""

    if not server:
        server = 'https://{}:{}'.format(CFG.get_key(['XNATSERVER']),
                                        CFG.get_key(['XNATPORT']))
    if username:
        password = getpass.getpass()
    else:
        #Moving away from storing credentials in text files
        username = os.environ["XNAT_USER"]
        password = os.environ["XNAT_PASS"]

    xnat = datman.xnat.xnat(server, username, password)
    return xnat

if __name__ == '__main__':
    main()
