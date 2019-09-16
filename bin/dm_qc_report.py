#!/usr/bin/env python
"""
Generates quality control reports on defined MRI data types. If no subject is
given, all subjects are submitted individually to the queue.

usage:
    dm-qc-report.py [options] <study>
    dm-qc-report.py [options] <study> <session>

Arguments:
    <study>           Name of the study to process e.g. ANDT
    <session>         Datman name of session to process e.g. DTI_CMH_H001_01_01

Options:
    --rewrite          Rewrite the html of an existing qc page
    --log-to-server    If set, all log messages will also be sent to the
                       configured logging server. This is useful when the
                       script is run with the Sun Grid Engine, since it swallows
                       logging messages.
    -q --quiet         Only report errors
    -v --verbose       Be chatty
    -d --debug         Be extra chatty

Details:
    This program QCs the data contained in <NiftiDir> and outputs a myriad of
    metrics as well as a report in <QCDir>. All work is done on a per-subject
    basis.

    **data directories**

    The folder structure expected is that generated by xnat-export.py:

        <NiftiDir>/
           subject1/
               file1.nii.gz
               file2.nii.gz
           subject2/
               file1.nii.gz
               file2.nii.gz

     One subfolder for each subject will be created under the <QCDir> folder.

     **gold standards**

     To check for changes to the MRI machine's settings over time this compares
     the header values found in JSONs produced by dcm2niix with the appropriate
     JSON file found in <StandardsDir>/<Tag>/filename.json.

     **configuration file**

     The locations of the nifti folder, qc folder, gold standards
     folder, log folder, and expected set of scans are read from the supplied
     configuration file with the following structure:

     paths:
       nii: '/archive/data/SPINS/data/nii'
       qc:  '/archive/data/SPINS/qc'
       std: '/archive/data/SPINS/metadata/standards'
       log: '/archive/data/SPINS/log'

     Sites:
       site1:
         XNAT_Archive: '/path/to/arc001'
         ExportInfo:
           - T1:  {Pattern: {'regex1', 'regex2'}, Count: n_expected}
           - DTI: {Pattern: {'regex1', 'regex2'}, Count: n_expected}
       site2 :
         XNAT_Archive: '/path/to/arc001'
         ExportInfo:
           - T1:  {Pattern: {'regex1', 'regex2'}, Count: n_expected}
           - DTI: {Pattern: {'regex1', 'regex2'}, Count: n_expected}
Requires:
    FSL
    QCMON
    MATLAB/R2014a - qa-dti phantom pipeline
    AFNI - abcd_fmri phantom pipeline
"""

import os, sys
import re
import glob
import time
import logging
import logging.handlers
import copy
import random
import string

import pandas as pd
import nibabel as nib
from docopt import docopt

import dm_header_checks as qc_headers
import datman.config
import datman.utils
import datman.scanid
import datman.scan
import datman.dashboard

logging.basicConfig(level=logging.WARN,
        format="[%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(os.path.basename(__file__))

config = None
REWRITE = False

SLICER_GAP = 2
SLICER_RES = 1600
SLICER_FMRI_RES = 600

def random_str(n):
    """generates a random string of length n"""
    return(''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(n)))

def slicer(fpath, pic, slicergap, picwidth):
    """
    Uses FSL's slicer function to generate a montage png from a nifti file
        fpath       -- submitted image file name
        slicergap   -- int of "gap" between slices in Montage
        picwidth    -- width (in pixels) of output image
        pic         -- fullpath to for output image
    """
    datman.utils.run("slicer {} -S {} {} {}".format(fpath,slicergap,picwidth,pic))

def slicesdir(fpath, pic):
    """
    Uses FSL's slicer function to generate a montage of three slices from
    each direction that matches FSL's slicesdir output
    """

    with datman.utils.make_temp_directory() as temp:
        img_command = "slicer {0} -s 1 "\
                "-x 0.4 {1}/grota.png -x 0.5 {1}/grotb.png -x 0.6 {1}/grotc.png "\
                "-y 0.4 {1}/grotd.png -y 0.5 {1}/grote.png -y 0.6 {1}/grotf.png "\
                "-z 0.4 {1}/grotg.png -z 0.5 {1}/groth.png -z 0.6 {1}/groti.png"\
                .format(fpath, temp)
        datman.utils.run(img_command)

        montage_command = "pngappend {0}/grota.png + {0}/grotb.png + "\
                "{0}/grotc.png + {0}/grotd.png + {0}/grote.png + {0}/grotf.png "\
                "+ {0}/grotg.png + {0}/groth.png + {0}/groti.png {1}"\
                .format(temp, pic)
        datman.utils.run(montage_command)

def add_image(qc_html, image, title=None):
    """
    Adds an image to the report.
    """
    if title:
        qc_html.write('<center> {} </center>'.format(title))

    relpath = os.path.relpath(image, os.path.dirname(qc_html.name))
    qc_html.write('<a href="'+ relpath + '" >')
    qc_html.write('<img src="' + relpath + '" >')
    qc_html.write('</a><br>\n')

    return qc_html

# PIPELINES
def ignore(filename, qc_dir, report):
    pass

def gather_input_req(nifti, pipeline):
    '''
    Contains input specification local variable and gathers requirements for each call
    nifti - contains nifti series instance
    subject - contains subject Scan instance
    pipeline - pipeline name (specified in tigrlab_config.yml)
    '''

    #Common requirements
    basename = os.path.join(os.path.dirname(nifti.path),datman.utils.nifti_basename(nifti.path))
    dcm = nifti.path.replace('/nii/','/dcm/').replace('.nii.gz','.dcm')

    #Input specifications and pipeline input mapping
    input_spec = {
            'anat'      :   ['qc-adni',             basename + '.nii.gz'],
            'fmri'      :   ['qc-fbirn-fmri',       basename + '.nii.gz'],
            'dti'       :   ['qc-fbirn-dti',        basename + '.nii.gz', basename + '.bvec', basename + '.bval'],
            'qa_dti'    :   ['qa-dti',              basename + '.nii.gz', basename + '.bvec', basename + '.bval',
                '--accel' if 'NO' in basename else ''],
            'abcd_fmri' :   ['qc-abcd-fmri',        basename + '.nii.gz']
            }

    reqs = None
    try:
        reqs = input_spec[pipeline]
    except KeyError:
        print('No QC pipeline available for {}. Skipping.'.format(nifti.tag,nifti.path))

    return reqs

def run_phantom_pipeline(nifti,qc_path,reqs):
    '''
    Used to formulate the BASH call to phantom qc pipeline.
    Performs input requirements gathering
    '''
    basename = datman.utils.nifti_basename(nifti.path)

    #Formulate pipeline command, there is an assumption that output is last argument here
    cmd = ' '.join([i for i in reqs]) + ' ' + os.path.join(qc_path,basename)

    logger.info('Running command: \n {}'.format(cmd))

    qc_output = os.path.join(qc_path,basename)
    #If any csv exists in qc path
    if not glob.glob(qc_output + '*.csv') or REWRITE:
          datman.utils.run(cmd)
    else:
        logger.info('QC on phantom {} with tag {}  already performed, skipping'.format(datman.utils.nifti_basename(nifti.path), nifti.tag))



def fmri_qc(file_name, qc_dir, report):
    base_name = datman.utils.nifti_basename(file_name)
    output_name = os.path.join(qc_dir, base_name)

    # check scan length
    script_output = output_name + '_scanlengths.csv'
    logger.info('Running qc-scanlength')
    if not os.path.isfile(script_output):
        datman.utils.run('qc-scanlength {} {}'.format(file_name, script_output))

    # check fmri signal
    script_output = output_name + '_stats.csv'
    logger.info('Running qc-fmri')
    if not os.path.isfile(script_output):
        datman.utils.run('qc-fmri {} {}'.format(file_name, output_name))

    slices_montage = output_name + "_montage.png"
    image_raw = output_name + '_raw.png'
    image_sfnr = output_name + '_sfnr.png'
    image_corr = output_name + '_corr.png'

    if not os.path.isfile(slices_montage):
        slicesdir(file_name, slices_montage)
    add_image(report, slices_montage)

    if not os.path.isfile(image_raw):
        slicer(file_name, image_raw, SLICER_GAP, SLICER_FMRI_RES)
    add_image(report, image_raw, title='BOLD montage')

    if not os.path.isfile(image_sfnr):
        slicer(os.path.join(qc_dir, base_name + '_sfnr.nii.gz'), image_sfnr,
                SLICER_GAP, SLICER_FMRI_RES)
    add_image(report, image_sfnr, title='SFNR map')

    if not os.path.isfile(image_corr):
        slicer(os.path.join(qc_dir, base_name + '_corr.nii.gz'), image_corr,
                SLICER_GAP, SLICER_FMRI_RES)
    add_image(report, image_corr, title='correlation map')

def anat_qc(filename, qc_dir, report):

    image = os.path.join(qc_dir, datman.utils.nifti_basename(filename) + '.png')
    if not os.path.isfile(image):
        slicer(filename, image, 5, SLICER_RES)
    add_image(report, image)

def dti_qc(filename, qc_dir, report):
    dirname = os.path.dirname(filename)
    basename = datman.utils.nifti_basename(filename)

    bvec = os.path.join(dirname, basename + '.bvec')
    bval = os.path.join(dirname, basename + '.bval')

    output_prefix = os.path.join(qc_dir, basename)
    output_file = output_prefix + '_stats.csv'
    if not os.path.isfile(output_file):
       datman.utils.run('qc-dti {} {} {} {}'.format(filename, bvec, bval,
                output_prefix))

    output_file = os.path.join(qc_dir, basename + '_spikecount.csv')
    if not os.path.isfile(output_file):
        datman.utils.run('qc-spikecount {} {} {}'.format(filename,
                os.path.join(qc_dir, basename + '_spikecount.csv'), bval))

    slices_montage = os.path.join(qc_dir, basename + "_montage.png")
    if not os.path.isfile(slices_montage):
        slicesdir(filename, slices_montage)
    image = os.path.join(qc_dir, basename + '_b0.png')
    if not os.path.isfile(image):
        slicer(filename, image, SLICER_GAP, SLICER_RES)
    add_image(report, slices_montage)
    add_image(report, image, title='b0 montage')
    add_image(report, os.path.join(qc_dir, basename + '_directions.png'),
            title='bvec directions')


def make_qc_command(subject_id, study, rewrite=False):
    arguments = docopt(__doc__)
    use_server = arguments['--log-to-server']
    verbose = arguments['--verbose']
    debug = arguments['--debug']
    quiet = arguments['--quiet']
    command = " ".join([__file__, study, subject_id])
    if verbose:
        command = " ".join([command, '-v'])
    if debug:
        command = " ".join([command, '-d'])
    if quiet:
        command = " ".join([command, '-q'])
    if use_server:
        command = " ".join([command, '--log-to-server'])

    if REWRITE or rewrite:
        command = command + ' --rewrite'

    return command

def qc_all_scans(config):
    """
    Creates a dm-qc-report.py command for each scan and submits all jobs to the
    queue. Phantom jobs are submitted in chained mode, which means they will run
    one at a time. This is currently needed because some of the phantom pipelines
    use expensive and limited software liscenses (i.e., MATLAB).
    """
    subs = get_all_subjects(config)

    for i, subject in enumerate(subs):
        if REWRITE or new_subject(subject, config):
            command = make_qc_command(subject, config.study_name)
        elif new_session(subject):
            command = make_qc_command(subject, config.study_name, rewrite=True)
        else:
            continue
        job_name = "qc_report_{}_{}_{}".format(time.strftime("%Y%m%d"),
                random_str(5), i)
        datman.utils.submit_job(command, job_name, "/tmp", system=config.system)

def get_all_subjects(config):
    nii_dir = config.get_path('nii')
    subject_nii_dirs = glob.glob(os.path.join(nii_dir, '*'))
    all_subs = [os.path.basename(path) for path in subject_nii_dirs]
    return all_subs

def new_subject(subject_id, config):
    subject = datman.scan.Scan(subject_id, config)
    if not os.path.exists(subject.qc_path):
        return True

    html_page = glob.glob(os.path.join(subject.qc_path, '*.html'))
    if html_page:
        return False

    if subject.is_phantom and len(os.listdir(subject.qc_path)) > 0:
        return False

    return True

def add_header_qc(nifti, qc_html, header_diffs):
    """
    Adds header-diff.log information to the report.
    """
    if not header_diffs:
        # Nothing to report on
        return

    # find lines in said log that pertain to the nifti
    scan_name = get_scan_name(nifti)
    lines = header_diffs[scan_name]

    if not lines:
        return

    table_header = """
    <table>
        <thead align=center>
            <tr>
                <th colspan=3><h3> {} header differences </h3></th>
            </tr>
            <tr>
                <th>Field</th>
                <th>Expected</th>
                <th>Actual</th>
            </tr>
        </thead>
        <tbody>
    """.format(nifti)

    qc_html.write(table_header)
    for field in sorted(lines):

        if field not in ['missing', 'error']:
            table_row = """
            <tr>
                <td>{field}</td>
                <td>{expected}</td>
                <td>{actual}</td>
            </tr>
            """.format(field=field, expected=lines[field]['expected'],
                    actual=lines[field]['actual'])
        else:
            table_row = """
            <tr>
                <td>{field}</td>
                <td>{message}</td>
            </tr>
            """.format(field=field, message=','.join(lines[field]))

        qc_html.write(table_row)
    qc_html.write('</tbody></table>\n')

def write_report_body(report, expected_files, subject, header_diffs, tag_settings):
    handlers = {
    # List of qc functions available mapped to 'qc_type' from user settings
        "anat"      : anat_qc,
        "fmri"      : fmri_qc,
        "dti"       : dti_qc,
        "ignore"    : ignore,
        "dmap_fmri" : anat_qc,
        "dmap_dmri" : anat_qc
    }
    for idx in range(0,len(expected_files)):
        series = expected_files.loc[idx,'File']
        if not series:
            continue

        logger.info("QC scan {}".format(series.path))
        report.write('<h2 id="{}">{}</h2>\n'.format(expected_files.loc[idx,'bookmark'],
                series.file_name))

        if series.tag not in tag_settings:
            logger.error("Tag not defined in config files: {}".format(series.tag))
            continue

        try:
            qc_type = tag_settings.get(series.tag, "qc_type")
        except KeyError:
            logger.info("qc_type not defined for tag {}. Skipping.".format(
                    series.tag))
            continue

        add_header_qc(series, report, header_diffs)

        # This is to deal with the fact that PDT2s are split and both images
        # need to be displayed
        new_series = get_series_to_add(series, subject)

        for series in new_series:
            try:
                handlers[qc_type](series.path, subject.qc_path, report)
            except KeyError:
                raise KeyError('series tag {} not defined in handlers:\n{}'.format(
                        series.tag, handlers))
            report.write('<br>')

def get_series_to_add(series, subject):
    """
    Returns the original series in a list if it's not a PDT2. If it is a PDT2,
    finds the split T2 and PD series and returns those in a list.
    """
    if series.tag != 'PDT2':
        return [series]

    try:
        t2 = get_split_image(subject, series.series_num, 'T2')
        split_series = [t2]
    except RuntimeError as e:
        logger.error("Can't add PDT2 {} to QC page. Reason: {}".format(
                series.path, e.message))
        return []

    try:
        pd = get_split_image(subject, series.series_num, 'PD')
    except RuntimeError as e:
        # A PD image may not exist if the PDT2 is actually just a T2...
        pass
    else:
        # If one does exist, add it to the results
        split_series.append(pd)

    return split_series

def get_split_image(subject, num, tag):
    image = None
    for series in subject.get_tagged_nii(tag):
        if series.series_num != num:
            continue
        image = series
    if not image:
        raise RuntimeError("No file found with tag {}".format(tag))
    return image

def find_all_tech_notes(path):
    """
    Extract the session identifier without the repeat label from the path:
    i.e. SPN01_CMH_0002_01_01 becomes SPN01_CMH_0002_01
    Search all folders matching the session identifier for potential
    technotes, returns a list of tuples: (repeat_number, file_path)
    """
    technotes = []
    base_dir = os.path.dirname(path)
    full_session = os.path.basename(path)
    ident = datman.scanid.parse(full_session)
    session = ident.get_full_subjectid_with_timepoint()
    session_paths = glob.glob(os.path.join(base_dir, session) + '*')
    for path in session_paths:
        base_name = os.path.basename(path)
        ident = datman.scanid.parse(base_name)
        # Some resource folders don't have a repeat number,
        # this is an error and should be ignored
        if ident.session:
            technote = find_tech_notes(path)
            if technote:
                technotes.append((ident.session, technote))

    return technotes

def find_tech_notes(path):
    """
    Search the file tree rooted at path for the tech notes pdf.

    If only one pdf is found it is assumed to be the tech notes. If multiple
    are found, unless one contains the string 'TechNotes', the first pdf is
    guessed to be the tech notes.
    """

    pdf_list = []
    for root, dirs, files in os.walk(path):
        for fname in files:
            if ".pdf" in fname:
                pdf_list.append(os.path.join(root, fname))


    if not pdf_list:
        return ""
    elif len(pdf_list) > 1:
        for pdf in pdf_list:
            file_name = os.path.basename(pdf)
            if 'technotes' in file_name.lower():
                return pdf

    return pdf_list[0]

def notes_expected(site, study_name):
    """
    Grabs 'USES_TECHNOTES' key in study config file to determine
    whether technotes are expected
    """

    try:
        technotes = config.get_key('USES_TECHNOTES', site=site)
    except datman.config.UndefinedSetting:
        technotes = False
    return technotes

def write_tech_notes_link(report, site, study_name, resource_path):
    """
    Adds a link to the tech notes for this subject to the given QC report
    """
    if not notes_expected(site, study_name):
        return

    tech_notes = find_all_tech_notes(resource_path)

    if not tech_notes:
        report.write('<p>Tech Notes not found</p>\n')
        return

    for technote in tech_notes:
        notes_path = os.path.relpath(os.path.abspath(technote[1]),
                                     os.path.dirname(report.name))
        report.write('<a href="{}">'.format(notes_path))
        report.write('Click Here to open Tech Notes - Session {}:'
                     .format(technote[0]))
        report.write('</a><br>')

def write_table(report, exportinfo, subject):
    report.write('<table><tr>'
                 '<th>Tag</th>'
                 '<th>File</th>'
                 '<th>Scanlength</th>'
                 '<th>Notes</th></tr>')

    for row in range(0,len(exportinfo)):
        #Fetch Scanlength from .nii File
        scan_nii_path = os.path.join(subject.nii_path, str(exportinfo.loc[row, 'File']))
        try:
            data = nib.load(scan_nii_path)
            try:
                scanlength = data.shape[3]
            except:
                #Note: this might be expected, e.g., for a T1
                logging.debug("{} exists but scanlength cannot be read.".format(scan_nii_path))
                scanlength = "N/A"
        except:
            logging.debug("{} does not exist; cannot read scanlength.".format(scan_nii_path))
            scanlength = "No file"
        report.write('<tr><td>{}</td>'.format(exportinfo.loc[row,'tag'])) ## table new row
        report.write('<td><a href="#{}">{}</a></td>'.format(exportinfo.loc[row,
                'bookmark'], exportinfo.loc[row,'File']))
        report.write('<td>{}</td>'.format(scanlength))
        report.write('<td><font color="#FF0000">{}</font></td>'\
                '</tr>'.format(exportinfo.loc[row,'Note'])) ## table new row
    report.write('</table>\n')

def write_report_header(report, subject_id):
    report.write('<HTML><TITLE>{} qc</TITLE>\n'.format(subject_id))
    report.write('<head>\n<style>\n'
                'body { font-family: futura,sans-serif;'
                '        text-align: center;}\n'
                'img {width:90%; \n'
                '   display: block\n;'
                '   margin-left: auto;\n'
                '   margin-right: auto }\n'
                'table { margin: 25px auto; \n'
                '        border-collapse: collapse;\n'
                '        text-align: left;\n'
                '        width: 90%; \n'
                '        border: 1px solid grey;\n'
                '        border-bottom: 2px solid black;} \n'
                'th {background: black;\n'
                '    color: white;\n'
                '    text-transform: uppercase;\n'
                '    padding: 10px;}\n'
                'td {border-top: thin solid;\n'
                '    border-bottom: thin solid;\n'
                '    padding: 10px;}\n'
                '</style></head>\n')

    report.write('<h1> QC report for {} <h1/>'.format(subject_id))

def generate_qc_report(report_name, subject, expected_files, header_diffs, config):
    tag_settings = config.get_tags(site=subject.site)
    try:
        with open(report_name, 'wb') as report:
            write_report_header(report, subject.full_id)
            write_table(report, expected_files, subject)
            write_tech_notes_link(report, subject.site, config.study_name,
                    subject.resource_path)
            write_report_body(report, expected_files, subject, header_diffs,
                    tag_settings)
    except:
        raise
    update_dashboard(subject, report_name, header_diffs)

def update_dashboard(subject, report_name, header_diffs):
    db_subject = datman.dashboard.get_subject(subject.full_id)
    if not db_subject:
        return
    try:
        db_subject.add_header_diffs(header_diffs)
    except Exception as e:
        logger.error("Failed to add header diffs for {} to dashboard database. "
                "Reason: {}".format(subject.full_id, e))
    db_subject.last_qc_repeat_generated = len(db_subject.sessions)
    db_subject.static_page = report_name
    db_subject.save()

def get_position(position_info):
    if isinstance(position_info, list):
        try:
            position = position_info.pop(0)
        except IndexError:
            ## More of this scan type than expected in config entry, assign
            ## last possible position
            position = 999
    else:
        position = position_info

    return position

def initialize_counts(export_info):
    # build a tag count dict
    tag_counts = {}
    expected_position = {}

    for tag in export_info.tags:
        tag_counts[tag] = 0
        # If ordering has been imposed on the scans get it for later sorting.
        try:
            ordering = export_info.get(tag, 'Order')
        except KeyError:
            ordering = [0]

        expected_position[tag] = ordering

    return tag_counts, expected_position

def find_expected_files(subject, config):
    """
    Reads the export_info from the config for this site and compares it to the
    contents of the nii folder. Data written to a pandas dataframe.
    """
    export_info = config.get_tags(subject.site)
    sorted_niftis = sorted(subject.niftis, key=lambda item: item.series_num)

    tag_counts, expected_positions = initialize_counts(export_info)

    # init output pandas data frame, counter
    idx = 0
    expected_files = pd.DataFrame(columns=['tag', 'File', 'bookmark', 'Note',
            'Sequence'])

    # tabulate found data in the order they were acquired
    for nifti in sorted_niftis:
        tag = nifti.tag

        # only check data that is defined in the config file
        if tag in export_info:
            expected_count = export_info.get(tag, 'Count')
        else:
            continue

        tag_counts[tag] += 1
        bookmark = tag + str(tag_counts[tag])
        if tag_counts[tag] > expected_count:
            notes = 'Repeated Scan'
        else:
            notes = ''

        position = get_position(expected_positions[tag])

        expected_files.loc[idx] = [tag, nifti, bookmark, notes,
                position]
        idx += 1

    # note any missing data
    for tag in export_info:
        expected_count = export_info.get(tag, 'Count')
        if tag_counts[tag] < expected_count:
            n_missing = expected_count - tag_counts[tag]
            notes = 'missing({})'.format(n_missing)
            expected_files.loc[idx] = [tag, '', '', notes,
                    expected_positions[tag]]
            idx += 1
    expected_files = expected_files.sort_values('Sequence')
    return(expected_files)

def find_json(series):
    json_path = series.path.replace(series.ext, ".json")
    if not os.path.exists(json_path):
        raise IOError("JSON not found for {}".format(series))
    return json_path

def get_standards(standard_dir, site):
    """
    Constructs a dictionary of standards for the given site.

    If a standards file name raises ParseException it will be logged and
    omitted from the standards dictionary.
    """
    glob_path = os.path.join(standard_dir, "*.json")

    standards = {}
    misnamed_files = []
    for item in glob.glob(glob_path):
        try:
            standard = datman.scan.Series(item)
        except datman.scanid.ParseException:
            misnamed_files.append(item)
            continue
        if standard.site == site:
            standards[standard.tag] = standard.path

    if misnamed_files:
        logging.error("Standards files misnamed, ignoring: \n" \
                "{}".format("\n".join(misnamed_files)))

    return standards

def get_scan_name(series):
    # Allows the dashboard to easily access diffs without needing to know
    # anything about naming scheme
    scan_name = series.file_name.replace("_" + series.description, "")\
            .replace(series.ext, "")
    return scan_name

def run_header_qc(subject, config):
    """
    For each json file found in 'niftis' find the matching site / tag file in
    'standards' and run dm_header_checks on these files. Differences are
    returned in a dictionary that maps the scan name to a dictionary of
    differences
    """
    standard_dir = config.get_path('std')
    standards_dict = get_standards(standard_dir, subject.site)
    tag_settings = config.get_tags(site=subject.site)

    try:
        ignored_headers = config.get_key('IgnoreHeaderFields', site=subject.site)
    except datman.config.UndefinedSetting:
        ignored_headers = []
    try:
        header_tolerances = config.get_key('HeaderFieldTolerance', site=subject.site)
    except datman.config.UndefinedSetting:
        header_tolerances = {}

    header_diffs = {}
    for series in subject.niftis:
        scan_name = get_scan_name(series)
        try:
            standard_json = standards_dict[series.tag]
        except KeyError:
            logger.debug('No standard with tag {} found in {}'.format(
                    series.tag, standard_dir))
            header_diffs[scan_name] = {'error': 'Gold standard not found'}
            continue

        try:
            series_json = find_json(series)
        except IOError:
            logger.debug('No JSON found for {}'.format(series))
            header_diffs[scan_name] = {'error': 'JSON not found'}
            continue

        try:
            qc_type = tag_settings.get(series.tag, "qc_type")
        except KeyError:
            logger.error("'qc_type' for tag {} not defined. If it's DTI the "
                    "bval check will be skipped.".format(series.tag))
            check_bvals = False
        else:
            check_bvals = qc_type == 'dti'

        diffs = qc_headers.construct_diffs(series_json, standard_json,
                ignored_fields=ignored_headers, tolerances=header_tolerances,
                dti=check_bvals)
        header_diffs[scan_name] = diffs

    return header_diffs

def qc_subject(subject, config):
    """
    subject :           The created Scan object for the subject_id this run
    config :            The settings obtained from project_settings.yml

    Returns the path to the qc_<subject_id>.html file
    """
    report_name = os.path.join(subject.qc_path, 'qc_{}.html'.format(subject.full_id))
    # header diff
    header_diffs_log = os.path.join(subject.qc_path, 'header-diff.json')

    if os.path.isfile(report_name):
        if not REWRITE:
            logger.debug("{} exists, skipping.".format(report_name))
            return
        os.remove(report_name)
        # This probably exists if you're rewriting, and needs to be removed to regenerate
        try:
            os.remove(header_diffs_log)
        except:
            pass

    header_diffs = run_header_qc(subject, config)
    if not datman.dashboard.dash_found and not os.path.isfile(header_diffs_log):
        qc_headers.write_diff_log(header_diffs, header_diffs_log)

    expected_files = find_expected_files(subject, config)

    new_entry = {str(subject): ''}
    try:
        # Update checklist even if report generation fails
        datman.utils.update_checklist(new_entry, config=config)
    except:
        logger.error("Error adding {} to checklist.".format(subject.full_id))

    try:
        generate_qc_report(report_name, subject, expected_files, header_diffs,
                config)
    except:
        logger.error("Exception raised during qc-report generation for {}. " \
                "Removing .html page.".format(subject.full_id), exc_info=True)
        if os.path.exists(report_name):
            os.remove(report_name)

    return report_name

def qc_phantom(subject, config):
    """
    subject:            The Scan object for the subject_id of this run
    config :            The settings obtained from project_settings.yml

    Phantom pipeline setup:
    Each pipeline has it's own dictionary entry in gather_input_reqs within input_spec
    Config 'qc_pha' keys in ExportSettings indicate which pipeline to use
    'qc_pha' set to 'default' will refer to the qc_type.
    So qc_pha is really used to indicate custom pipelines that are non-standard.
    """

    export_tags = config.get_tags(site=subject.site)

    logger.debug('qc {}'.format(subject))

    for nifti in subject.niftis:
        tag = get_pha_qc_type(export_tags, nifti.tag)
        #Gather pipeline input requirements and run if pipeline exists for tag
        input_req = gather_input_req(nifti, tag)
        if input_req:
            run_phantom_pipeline(nifti, subject.qc_path, input_req)

def get_pha_qc_type(export_tags, nii_tag):
    #Use qc_type if default option is set or 'qc_pha' is missing
    try:
        tag = export_tags.get(nii_tag, 'qc_pha')
    except KeyError:
        logger.info('qc_pha not set for tag {}, using qc_type default '
                'instead'.format(nii_tag))
        tag = 'default'
    if tag == 'default':
        tag = export_tags.get(nii_tag,'qc_type')
    return tag

def qc_single_scan(subject, config):
    """
    Perform QC for a single subject or phantom. Return the report name if one
    was created.
    """
    if subject.is_phantom:
        logger.info("QC phantom {}".format(subject.nii_path))
        qc_phantom(subject, config)
        return

    logger.info("QC {}".format(subject.nii_path))
    qc_subject(subject, config)
    return

def verify_input_paths(path_list):
    """
    Ensures that each path in path_list exists. If a path (or paths) do not
    exist this is logged and sys.exit is raised.
    """
    broken_paths = []
    for path in path_list:
        if not os.path.exists(path):
            broken_paths.append(path)

    if broken_paths:
        logging.error("The following path(s) required for input " \
                "do not exist: \n" \
                "{}".format("\n".join(broken_paths)))
        sys.exit(1)

def new_session(subject):
    """
    Detects if a repeat has been pulled in since the QC page was originally
    generated.

    WARNING: If it cannot find the dashboard/database pages will not be updated
    to add the new session(s)
    """

    db_subject = datman.dashboard.get_subject(subject)

    # If dashboard cant be found it cant detect repeats, return false
    if not db_subject:
        logger.warning('Cannot find subject {} in dashboard database. They may '
                'be missing, or database may be inaccessible.'.format(subject))
        return False

    if db_subject.last_qc_repeat_generated < len(db_subject.sessions):
        return True
    return False

def prepare_scan(subject_id, config):
    """
    Makes a new Scan object for this participant, clears out any empty files
    from needed directories and ensures that if needed input directories do
    not exist that the program exits.
    """
    global REWRITE
    try:
        subject = datman.scan.Scan(subject_id, config)
    except datman.scanid.ParseException as e:
        logger.error(e, exc_info=True)
        sys.exit(1)

    if new_session(subject_id):
        REWRITE = True
    verify_input_paths([subject.nii_path])

    qc_dir = datman.utils.define_folder(subject.qc_path)
    # If qc_dir already existed and had empty files left over clean up
    datman.utils.remove_empty_files(qc_dir)
    return subject

def get_config(study):
    """
    Retrieves the configuration information for this site and checks
    that the expected paths are all defined.

    Will raise KeyError if an expected path has not been defined for this study.
    """
    logger.info('Loading config')

    try:
        config = datman.config.config(study=study)
    except:
        logger.error("Cannot find configuration info for study {}".format(study))
        sys.exit(1)

    required_paths = ['dcm', 'nii', 'qc', 'std', 'meta']

    for path in required_paths:
        try:
            config.get_path(path)
        except KeyError:
            logger.error('Path {} not found for project: {}'
                         .format(path, study))
            sys.exit(1)

    return config

def add_server_handler(config):
    server_ip = config.get_key('LOGSERVER')
    server_handler = logging.handlers.SocketHandler(server_ip,
            logging.handlers.DEFAULT_TCP_LOGGING_PORT)
    logger.addHandler(server_handler)

def main():
    global config
    global REWRITE

    arguments = docopt(__doc__)
    use_server = arguments['--log-to-server']
    verbose = arguments['--verbose']
    debug = arguments['--debug']
    quiet = arguments['--quiet']
    study = arguments['<study>']
    session = arguments['<session>']
    REWRITE = arguments['--rewrite']


    config = get_config(study)

    if use_server:
        add_server_handler(config)

    if quiet:
        logger.setLevel(logging.ERROR)
    if verbose:
        logger.setLevel(logging.INFO)
    if debug:
        logger.setLevel(logging.DEBUG)

    if session:
        subject = prepare_scan(session, config)
        qc_single_scan(subject, config)
        return

    qc_all_scans(config)

if __name__ == "__main__":
    main()
