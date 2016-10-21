#!/usr/bin/env python
"""
This pre-processes fmri data using the settings found in project_config.yml
If subject is not defined, this runs in batch mode for all subjects.

Usage:
    dm-proc-fmri.py [options] <config>

Arguments:
    <config>         configuration .yml file

Options:
    --subject SUBJID subject name to run on
    --debug          debug logging
    --dry-run        don't do anything

DEPENDENCIES
    + python
    + afni
    + fsl
    + epitome
"""

from datman.docopt import docopt
import datman as dm
import yaml
import logging
import os, sys
import glob
import shutil
import tempfile
import time

logging.basicConfig(level=logging.WARN, format="[%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(os.path.basename(__file__))

def check_inputs(config, tag, path, expected_tags):
    """
    Ensures we have the same number of input files as we have defined in
    ExportInfo.
    """
    if not expected_tags:
        raise Exception('ERROR: expected tag {} not found in {}'.format(tag, path))
    n_found = len(expected_tags)

    site = dm.scanid.parse_filename(expected_tags[0])[0].site
    n_expected = config['Sites'][site]['ExportInfo'][tag]['Count']

    if n_found != n_expected:
        raise Exception('ERROR: number of files found with tag {} was {}, expected {}'.format(tag, n_found, n_expected))

def export_directory(source, destination):
    """
    Copies a folder from a source to a destination, throwing an error if it fails.
    If the destination folder already exists, it will be removed and replaced.
    """
    if os.path.isdir(destination):
        try:
            shutil.rmtree(destination)
        except:
            raise Exception("failed to remove existing folder {}".format(destination))
    try:
        shutil.copytree(source, destination)
    except:
        raise Exception("ERROR: failed to export {} to {}".format(source, destination))

def export_file(source, destination):
    """
    Copies a file from a source to a destination, throwing an error if it fails.
    """
    if not os.path.isfile(destination):
        try:
            shutil.copyfile(source, destination)
        except IOError, e:
            raise Exception('Problem exporting {} to {}'.format(source, destination))

def export_file_list(pattern, files, output_dir):
    """
    Copies, from a list of files, all files containing some substring into
    an output directory.
    """
    matches = filter(lambda x: pattern in x, files)
    for match in matches:
        output = os.path.join(output_dir, os.path.basename(match))
        try:
            export_file(match, output)
        except:
            pass

def outputs_exist(output_dir, expected_names):
    """
    Returns True if all expected outputs exist in the target directory,
    otherwise, returns false.
    """
    files = glob.glob(output_dir + '/*')
    found = 0

    for output in expected_names:
        if filter(lambda x: output in x, files):
            found += 1

    if found == len(expected_names):
        logger.debug('outputs found for output directory {}'.format(output_dir))
        return True

    return False

def run_epitome(path, config):
    """
    Finds the appropriate inputs for input subject, builds a temporary epitome
    folder, runs epitome, and finally copies the outputs to the fmri_dir.
    """
    subject = os.path.basename(path)
    nii_dir = config['paths']['nii']
    t1_dir = config['paths']['hcp']
    fmri_dir = dm.utils.define_folder(config['paths']['fmri'])
    experiments = config['fmri'].keys()

    # run file collection --> epitome --> export for each study
    for exp in experiments:

        # collect the files needed for each experiment
        expected_names = config['fmri'][exp]['export']
        expected_tags = config['fmri'][exp]['tags']
        output_dir = dm.utils.define_folder(os.path.join(fmri_dir, exp, subject))

        if type(expected_tags) == str:
            expected_tags = [expected_tags]

        # locate functional data
        files = glob.glob(path + '/*')
        functionals = []
        for tag in expected_tags:
            candidates = filter(lambda x: tag in x, files)
            candidates.sort()
            try:
                check_inputs(config, tag, path, candidates)
            except Exception as m:
                logger.debug('ERROR: {}'.format(m))
                continue
            functionals.extend(candidates)

        # locate anatomical data
        anat_path = os.path.join(t1_dir, os.path.basename(path), 'T1w')
        files = glob.glob(anat_path + '/*')
        anatomicals = []
        for anat in ['aparc+aseg.nii.gz', 'aparc.a2009s+aseg.nii.gz', 'T1w_brain.nii.gz']:
            if not filter(lambda x: anat in x, files):
                logger.error('ERROR: expected anatomical {} not found in {}'.format(anat, anat_path))
                sys.exit(1)
            anatomicals.append(os.path.join(anat_path, anat))

        # don't run if the outputs of epitome already exist
        if outputs_exist(output_dir, expected_names):
            continue

        # create and populate epitome directory
        epi_dir = tempfile.mkdtemp()
        dm.utils.make_epitome_folders(epi_dir, len(functionals))
        epi_t1_dir = '{}/TEMP/SUBJ/T1/SESS01'.format(epi_dir)
        epi_func_dir = '{}/TEMP/SUBJ/FUNC/SESS01'.format(epi_dir)

        try:
            shutil.copyfile(anatomicals[0], '{}/anat_aparc_brain.nii.gz'.format(epi_t1_dir))
            shutil.copyfile(anatomicals[1], '{}/anat_aparc2009_brain.nii.gz'.format(epi_t1_dir))
            shutil.copyfile(anatomicals[2], '{}/anat_T1_brain.nii.gz'.format(epi_t1_dir))
            for i, d in enumerate(functionals):
                shutil.copyfile(d, '{}/RUN{}/FUNC.nii.gz'.format(epi_func_dir, '%02d' % (i + 1)))
        except IOError as e:
            logger.error("ERROR: unable to copy files to {}\n{}".format(epi_dir, e))
            continue

        # collect command line options
        dims = config['fmri'][exp]['dims']
        tr = config['fmri'][exp]['tr']
        delete = config['fmri'][exp]['del']
        pipeline =  config['fmri'][exp]['pipeline']

        pipeline = os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir, 'assets/{}'.format(pipeline))
        if not os.path.isfile(pipeline):
            raise Exception('invalid pipeline {} defined!'.format(pipeline))

        # run epitome
        command = '{} {} {} {} {}'.format(pipeline, epi_dir, delete, tr, dims)
        rtn, out, err = dm.utils.run(command)
        output = '\n'.join([out, err]).replace('\n', '\n\t')
        if rtn != 0:
            logger.debug("epitome script failed: {}\n{}".format(command, output))
            continue
        else:
            pass

        # export fmri data
        epitome_outputs = glob.glob(epi_func_dir + '/*')
        for name in expected_names:
            try:
                matches = filter(lambda x: 'func_' + name in x, epitome_outputs)
                matches.sort()

                # attempt to export the defined epitome stages for all runs
                if len(matches) != len(functionals):
                    logger.error('epitome output {} not created for all inputs'.format(name))
                    continue
                for i, match in enumerate(matches):
                    func_basename = dm.utils.splitext(os.path.basename(functionals[i]))[0]
                    func_output = os.path.join(output_dir, func_basename + '_{}.nii.gz'.format(name))
                    export_file(match, func_output)

                # export all anatomical / registration information
                export_file_list('anat_', epitome_outputs, output_dir)
                export_file_list('reg_',  epitome_outputs, output_dir)
                export_file_list('mat_',  epitome_outputs, output_dir)

                # export PARAMS folder
                export_directory(os.path.join(epi_func_dir, 'PARAMS'), os.path.join(output_dir, 'PARAMS'))

            except ProcessingError as p:
                logger.error('ERROR: {}'.format(p))
                continue

        # remove temporary directory
        shutil.rmtree(epi_dir)

def main():
    """
    Runs fmri data through the specified epitome script.
    """
    arguments = docopt(__doc__)

    config_file = arguments['<config>']
    scanid      = arguments['--subject']
    debug       = arguments['--debug']
    dryrun      = arguments['--dry-run']

    # configure logging
    logging.info('Starting')
    if debug:
        logger.setLevel(logging.DEBUG)

    with open(config_file, 'r') as stream:
        config = yaml.load(stream)

    for k in ['nii', 'fmri', 'hcp']:
        if k not in config['paths']:
            print("ERROR: paths:{} not defined in {}".format(k, config_file))
            sys.exit(1)

    for x in config['fmri'].iteritems():
        for k in ['dims', 'del', 'pipeline', 'tags', 'export', 'tr']:
            if k not in x[1].keys():
                print("ERROR: fmri:{}:{} not defined in {}".format(x[0], k, config_file))
                sys.exit(1)

    nii_dir = config['paths']['nii']

    if scanid:
        path = os.path.join(nii_dir, scanid)
        if '_PHA_' in scanid:
            sys.exit('Subject {} if a phantom, cannot be analyzed'.format(scanid))
        try:
            run_epitome(path, config)
        except Exception as e:
            logging.error(e)
            sys.exit(1)

    # run in batch mode
    else:
        subjects = []
        nii_dirs = glob.glob('{}/*'.format(nii_dir))

        # find subjects where at least one expected output does not exist
        for path in nii_dirs:
            subject = os.path.basename(path)

            if dm.scanid.is_phantom(subject):
                logger.debug("Subject {} is a phantom. Skipping.".format(subject))
                continue

            fmri_dir = dm.utils.define_folder(config['paths']['fmri'])
            for exp in config['fmri'].keys():
                expected_names = config['fmri'][exp]['export']
                subj_dir = os.path.join(fmri_dir, exp, subject)
                if not outputs_exist(subj_dir, expected_names):
                    subjects.append(subject)
                    break

        subjects = list(set(subjects))

        # submit a list of calls to ourself, one per subject
        commands = []
        for subject in subjects:
            commands.append(" ".join([__file__, config_file, '--subject {}'.format(subject)]))

        if commands:
            logger.debug('queueing up the following commands:\n'+'\n'.join(commands))
            for cmd in commands:
                jobname = 'dm_fmri_{}'.format(time.strftime("%Y%m%d-%H%M%S"))
                logfile = '/tmp/{}.log'.format(jobname)
                errfile = '/tmp/{}.err'.format(jobname)
                rtn, out, err = dm.utils.run('echo {} | qsub -V -q main.q -o {} -e {} -N {}'.format(cmd, logfile, errfile, jobname))

                if rtn != 0:
                    logger.error("Job submission failed. Output follows.")
                    logger.error("stdout: {}\nstderr: {}".format(out,err))
                    sys.exit(1)

if __name__ == "__main__":
    main()

