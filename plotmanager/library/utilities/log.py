import dateparser
import logging
import os
import psutil
import re
import socket
import requests

from plotmanager.library.utilities.instrumentation import increment_plots_completed
from plotmanager.library.utilities.notifications import send_notifications
from plotmanager.library.utilities.print import pretty_print_time
from datetime import datetime, timedelta


def get_log_file_name(log_directory, job, datetime):
    return os.path.join(log_directory, f'{job.name}_{str(datetime).replace(" ", "_").replace(":", "_").replace(".", "_")}.log')


def _analyze_log_end_date(contents):
    match = re.search(r'total time = ([\d\.]+) seconds\. CPU \([\d\.]+%\) [A-Za-z]+\s([^\n]+)\n', contents, flags=re.I)
    if not match:
        return False
    total_seconds, date_raw = match.groups()
    total_seconds = pretty_print_time(int(float(total_seconds)))
    parsed_date = dateparser.parse(date_raw)
    return dict(
        total_seconds=total_seconds,
        date=parsed_date,
    )


def _get_date_summary(analysis):
    summary = analysis.get('summary', {})
    for file_path in analysis['files'].keys():
        if analysis['files'][file_path]['checked']:
            continue
        analysis['files'][file_path]['checked'] = True
        end_date = analysis['files'][file_path]['data']['date'].date()
        if end_date not in summary:
            summary[end_date] = 0
        summary[end_date] += 1
    analysis['summary'] = summary
    return analysis


def _get_regex(pattern, string, flags=re.I):
    return re.search(pattern, string, flags=flags).groups()


def get_completed_log_files(log_directory, skip=None):
    if not skip:
        skip = []
    files = {}
    for file in os.listdir(log_directory):
        if file[-4:] not in ['.log', '.txt']:
            continue
        file_path = os.path.join(log_directory, file)
        if file_path in skip:
            continue
        f = open(file_path, 'r')
        try:
            contents = f.read()
        except UnicodeDecodeError:
            continue
        f.close()
        if 'Total time = ' not in contents:
            continue
        files[file_path] = contents
    return files


def analyze_log_dates(log_directory, analysis):
    files = get_completed_log_files(log_directory, skip=list(analysis['files'].keys()))
    for file_path, contents in files.items():
        data = _analyze_log_end_date(contents)
        if data is None:
            continue
        analysis['files'][file_path] = {'data': data, 'checked': False}
    analysis = _get_date_summary(analysis)
    return analysis

def check_phase_times(log_directory, view_settings):
    files = get_completed_log_files(log_directory)
    for file_path, contents in files.items():
        phase_times, phase_dates = get_phase_info(contents, view_settings, pretty_print=True)
        print(f"File: {file_path}, Total: {phase_times[6]}, Phases : {phase_times[1]} / {phase_times[2]} / {phase_times[3]} / {phase_times[4]} / {phase_times.get(5,'')}")

def analyze_log_times(log_directory):
    total_times = {1: 0, 2: 0, 3: 0, 4: 0}
    line_numbers = {1: [], 2: [], 3: [], 4: []}
    count = 0
    files = get_completed_log_files(log_directory)
    for file_path, contents in files.items():
        count += 1
        phase_times, phase_dates = get_phase_info(contents, pretty_print=False)
        for phase, seconds in phase_times.items():
            total_times[phase] += seconds
        splits = contents.split('Time for phase')
        phase = 0
        new_lines = 1
        for split in splits:
            phase += 1
            if phase >= 5:
                break
            new_lines += split.count('\n')
            line_numbers[phase].append(new_lines)

    for phase in range(1, 5):
        print(f'  phase{phase}_line_end: {int(round(sum(line_numbers[phase]) / len(line_numbers[phase]), 0))}')

    for phase in range(1, 5):
        print(f'  phase{phase}_weight: {round(total_times[phase] / sum(total_times.values()) * 100, 2)}')


def get_phase_info(contents, view_settings=None, pretty_print=True):
    if not view_settings:
        view_settings = {}
    phase_times = {}
    phase_dates = {}

    for phase in range(1, 7):
        if(phase <= 4):
            match = re.search(rf'time for phase {phase} = ([\d\.]+) seconds\. CPU \([\d\.]+%\) [A-Za-z]+\s([^\n]+)\n', contents, flags=re.I)
        elif(phase == 5):
            match = re.search(rf'Copy time = ([\d\.]+) seconds\. CPU \([\d\.]+%\) [A-Za-z]+\s([^\n]+)\n', contents, flags=re.I)
        elif(phase ==6):
            match = re.search(rf'Total time = ([\d\.]+) seconds\. CPU \([\d\.]+%\) [A-Za-z]+\s([^\n]+)\n', contents, flags=re.I)
        if match:
            seconds, date_raw = match.groups()
            seconds = float(seconds)
            phase_times[phase] = seconds
            parsed_date = dateparser.parse(date_raw)
            phase_dates[phase] = parsed_date

    return phase_times, phase_dates


def get_progress(line_count, progress_settings):
    phase1_line_end = progress_settings['phase1_line_end']
    phase2_line_end = progress_settings['phase2_line_end']
    phase3_line_end = progress_settings['phase3_line_end']
    phase4_line_end = progress_settings['phase4_line_end']
    phase1_weight = progress_settings['phase1_weight']
    phase2_weight = progress_settings['phase2_weight']
    phase3_weight = progress_settings['phase3_weight']
    phase4_weight = progress_settings['phase4_weight']
    progress = 0
    if line_count > phase1_line_end:
        progress += phase1_weight
    else:
        progress += phase1_weight * (line_count / phase1_line_end)
        return progress
    if line_count > phase2_line_end:
        progress += phase2_weight
    else:
        progress += phase2_weight * ((line_count - phase1_line_end) / (phase2_line_end - phase1_line_end))
        return progress
    if line_count > phase3_line_end:
        progress += phase3_weight
    else:
        progress += phase3_weight * ((line_count - phase2_line_end) / (phase3_line_end - phase2_line_end))
        return progress
    if line_count > phase4_line_end:
        progress += phase4_weight
    else:
        progress += phase4_weight * ((line_count - phase3_line_end) / (phase4_line_end - phase3_line_end))
    return progress

def check_error(work, contents, notification_settings):
    match = re.search(rf'Retrying in five minutes', contents, flags=re.I)
    if(match):
        send_notifications(
                    title='Plotting Error',
                    body=f"pid: {work.pid}, job: {work['job']['name']} on {socket.gethostname()} has an error.",
                    settings=notification_settings,
                )

def check_log_progress(jobs, running_work, progress_settings, notification_settings, view_settings,
                       instrumentation_settings):
    for pid, work in list(running_work.items()):
        logging.info(f'Checking log progress for PID: {pid}')
        if not work.log_file:
            continue
        f = open(work.log_file, 'r')
        data = f.read()
        f.close()

        line_count = (data.count('\n') + 1)

        progress = get_progress(line_count=line_count, progress_settings=progress_settings)

        phase_times, phase_dates = get_phase_info(data)
        check_error(work, data, notification_settings)
        
        current_phase = 1
        if phase_times:
            current_phase = max(phase_times.keys()) + 1
            current_phase_time = str(datetime.now() - phase_dates[max(phase_dates.keys())])
            work.current_phase_time = ':'.join(current_phase_time.split(':')[:2])
            
        work.phase_times = phase_times
        work.phase_dates = phase_dates
        work.current_phase = current_phase
        work.progress = f'{progress:.2f}%'

        if psutil.pid_exists(pid) and 'renamed final file from ' not in data.lower():
            logging.info(f'PID still alive: {pid}')
            continue

        logging.info(f'PID no longer alive: {pid}')
        for job in jobs:
            if not job or not work or not work.job:
                continue
            if job.name != work.job.name:
                continue
            logging.info(f'Removing PID {pid} from job: {job.name}')
            if pid in job.running_work:
                job.running_work.remove(pid)
            job.total_running -= 1
            job.total_completed += 1
            increment_plots_completed(increment=1, job_name=job.name, instrumentation_settings=instrumentation_settings)


            try:
                headers={'Content-type':'application/json', 'Accept':'application/json'}
                url = "http://192.168.0.173:5000/api/Plot/Create"
                #url = "http://localhost:57097/api/Plot/Create"
                plot = {
                    'jobName': job.name,
                    'kSize': work.k_size if work.k_size else (work.job.size if work.job.size else 32),
                    'totalSeconds': int(phase_times.get(6,0)),
                    'phase1Seconds': int(phase_times.get(1,0)),
                    'phase2Seconds': int(phase_times.get(2,0)),
                    'phase3Seconds': int(phase_times.get(3,0)),
                    'phase4Seconds': int(phase_times.get(4,0)),
                    'copySeconds': int(phase_times.get(5,0)),
                    'machine': socket.gethostname(),
                    # 'tempPath': job.temporary_directory,
                    # 'temp2Path': job.temporary2_directory,
                    # 'destPath': job.destination_directory,
                    }

                requests.post(url, json=plot, headers = headers)
                send_notifications(
                    title='Api called.',
                    body=f"json: {plot}",
                    settings=notification_settings,
                )
            except:
                send_notifications(
                    title='Record to DB Error, so send notification',
                    body=f"job {job.total_completed} - {job.name} finished on {socket.gethostname()}.\nTotal Time: {phase_times.get(6,0)},\nPhases: {phase_times.get(1,0)} / {phase_times.get(2,0)} / {phase_times.get(3,0)} / {phase_times.get(4,0)}\nCopy Time: {phase_times.get(5,0)}",
                    settings=notification_settings,
                )
            break
        del running_work[pid]
