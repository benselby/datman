#!/usr/bin/env python
"""FACES Task Parser

Converts eprime text file for FACES task into BIDS .tsv files.

Usage: 
    dm_parse_faces.py [options] <study> [<session>]  
    dm_parse_faces.py [options] <study> [<session>] 
    dm_parse_faces.py [options] <study> [<session>] [--output-dir=<out_dir>] 

Arguments:
    <study>     Name of the study to process e.g. OPT
    <session>   Datman name of session to process e.g. OPT01_UP1_UP10044_02_03

Options:
    --debug                 Set log level to debug
    --output-dir=<out_dir>  Specify an alternate output directory 
    --dry-run               Don't actually write any output

Outputs the trial number, onset time, accurracy, and reaction time values 
for each trial.

Originally written by Ella Wiljer, 2018
BIDS-ified by Gabi Herman, 21 Nov 2018
"""

from docopt import docopt
import codecs
import logging
import pandas as pd
import numpy as np
import re
import os
import glob

import datman.config
import datman.scanid

logging.basicConfig(level=logging.WARN,
                    format="[%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(os.path.basename(__file__))

_to_esc = re.compile(r'\s|()')


def _esc_fname(match):
    return '\\' + match.group(0)


# function to read the eprime file
def read_eprime(eprimefile):
    eprime = codecs.open(eprimefile, "r", encoding="utf-16", errors="strict")
    lines = []
    for line in eprime:
        lines.append(str(line))
    return lines


# find all data entries in one dataset
def find_all_data(eprime, tag):
    dataset = [(i, s) for i, s in enumerate(eprime) if tag in s]
    return dataset


def findnum(ln):
    try:
        txtnum = re.findall('(\d+)\r\n', ln)
        return float(txtnum[0])
    except ValueError:
        return txtnum[0]


def get_event_value(eprime, event):

    events = find_all_data(eprime, event)
    if not events:
        return np.nan
    elif len(events) > 1:
        logger.error("Was expecting only one event, but received multiple!")
        raise ValueError

    return findalphanum(events[0][1])


def event_is_empty(e):
    return e.strip().endswith(':')


def findalphanum(ln):

    # Check if any values exist
    if event_is_empty(ln):
        return np.nan
    try:
        txtnum = re.findall('(?<=: )[A-Za-z0-9]+', ln)[0]
    except IndexError:
        logger.error(f"Value found is unexpected!: {ln}")
        raise
    return txtnum


def get_event_response(eprime, rsp_event):
    resp = get_event_value(eprime, rsp_event)
    return map_response(resp)


def map_response(x):
    '''
    Some FACES task files use "c" and "d" instead of 1,2
    '''

    if pd.isnull(x):
        return x

    if x.isdigit():
        return x

    mapdict = {'c': 1, 'd': 2}
    try:
        res = int(mapdict[x])
    except KeyError:
        logger.error(f"Value \'{x}\' is not numeric or matches 'c or d'")

    return res


def main():

    arguments = docopt(__doc__)
    out_dir = arguments['--output-dir']
    session = arguments['<session>']
    study = arguments['<study>']
    debug = arguments["--debug"]
    dryrun = arguments["--dry-run"]

    if debug:
        logger.setLevel(logging.DEBUG)

    if dryrun:
        logger.info("Dry run - will not write any output")

    config = datman.config.config(study=study)

    task_path = config.get_path("task")
    nii_path = config.get_path("nii")

    if not session:
        sessions = os.listdir(task_path)

    else:
        sessions = [session]
        logger.info(f"Running FACES parser for session {session}")

    for ses in sessions:
        logger.info(f"Parsing {ses}...")

        try:
            ident = datman.scanid.parse(ses)
        except datman.scanid.ParseException:
            logger.error(f"Skipping task folder with malformed ID {ses}")
            continue
        ses_path = os.path.join(task_path, ses)

        task_files = glob.glob(ses_path + '/*.txt')
        if not task_files:
            logger.info(f"No .txt files found for {ses}, skipping.")
            continue

        for eprimefile in task_files:
            logger.info(f"Found file: {eprimefile}")
            try:
                eprime = read_eprime(eprimefile)
            except UnicodeError as e:
                logger.error(f"Cannot parse {eprimefile}: {e}")
                continue

            init_tag = find_all_data(eprime, "Procedure: InitialTR\r\n")
            init_start = np.empty([len(init_tag)], dtype=int)
            init_end = np.empty([len(init_tag)], dtype=int)

            for i, ind_init in enumerate(init_tag):
                if i < len(init_tag) - 1:
                    init_end[i] = init_tag[i+1][0]
                elif i==len(init_tag)-1:
                    init_end[i] = len(eprime) - 1
                init_start[i] = ind_init[0]

            init_blocks = [ eprime[s:e] for s, e in zip(init_start, init_end) ]
            
            syncOT = float('nan')
            for b in init_blocks:
                new_syncOT = get_event_value(b, 'SyncSlide.OnsetTime:')
                stim = get_event_value(b, 'Stimulus:')
                if not np.isnan(int(new_syncOT)) and stim=='4':
                    syncOT = new_syncOT

            # tag the trials to obtain the data for each trial
            taglist = find_all_data(eprime, "Procedure: TrialsPROC\r\n")

            if not taglist:
                logger.error(f"No trials found for {ses} - skipping")
                continue

            trial_start = np.empty([len(taglist)], dtype=int)
            trial_end = np.empty([len(taglist)], dtype=int)

            for i, ind_trial_proc in enumerate(taglist):
                if (i < (len(taglist)) - 1):
                    trial_end[i] = taglist[i + 1][0]
                elif (i == (len(taglist)) - 1):
                    trial_end[i] = len(eprime) - 1

                trial_start[i] = ind_trial_proc[0]

            trial_blocks = [
                eprime[s:e] for s, e in zip(trial_start, trial_end)
            ]

            entries = []
            for b in trial_blocks:
                stimOT = get_event_value(b, 'StimSlide.OnsetTime:')
                rel_stimOT = (float(stimOT) - float(syncOT))/1000 # convert from ms to seconds
                entries.append({
                    'onset':
                    rel_stimOT,
                    'duration':
                    get_event_value(b, 'StimSlideOnsetToOnsetTime:'),
                    'trial_type':
                    'Shapes' if 'Shape' in str(b) else 'Faces',
                    'response_time':
                    get_event_value(b, 'StimSlide.RT:'),
                    'accuracy':
                    get_event_value(b, 'StimSlide.ACC:'),
                    'correct_response':
                    map_response(get_event_value(b, 'CorrectResponse:')),
                    'participant_response':
                    map_response(get_event_value(b, 'StimSlide.RESP:'))
                })

            data = pd.DataFrame.from_dict(entries).astype({
                    "onset": np.float,
                    "duration": np.float,
                    "response_time": np.float,
                    "accuracy": np.float,
                    "correct_response": np.float,
                    "participant_response": np.float
                    })\
                    .astype({
                        "correct_response": "Int64",
                        "participant_response": "Int64",
                        "accuracy": "Int64"
                    })

            log_head, log_tail = os.path.split(eprimefile)

            sub_id = os.path.basename(log_head)

            if not out_dir:
                out_dir = os.path.join(
                    nii_path, ident.get_full_subjectid_with_timepoint())

            file_name = os.path.join(out_dir, f"{ses}_FACES.tsv")
            if not os.path.exists(os.path.dirname(file_name)):
                os.makedirs(os.path.dirname(file_name))

            if not dryrun:
                logger.info(f"Saving output to {file_name}")
                data.to_csv(file_name, sep='\t', index=False)
            else:
                logger.info(f"Dry run - would save to {file_name}")


if __name__ == '__main__':
    main()
