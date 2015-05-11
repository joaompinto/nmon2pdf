#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
 nmon2pdf .py - Generate a PDF report from nmon data
 Developer: João Pinto

 Usage:
    nmon2pdf.py input_directory
"""

import sys
import csv
from itertools import groupby
import matplotlib.pyplot as plt
import dateutil.parser as parser
import matplotlib.dates as mdates
import matplotlib.ticker
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from os.path import join, basename, isdir
from glob import glob
from optparse import OptionParser
import re

csv.field_size_limit(sys.maxsize)

START_HOUR = 0
END_HOUR = 24

SHOW_FIELDS = ['CPU_ALL']


def med(x):
    return sum(x) / len(x)

def _parse_cmd():
    cmd_parser = OptionParser()
    cmd_parser.add_option("-d", "--date-filter", dest="date_filter",
                          help="Filter on date", default=None)
    cmd_parser.add_option("-g", "--group-by", dest="group_by",
                          help="Group by date/time interval", default=None)
    cmd_parser.add_option("-y", "--max-y", dest="max_y",
                          help="Group by date/time interval", default=None)
    (options, args) = cmd_parser.parse_args()
    if len(args) < 0:
        cmd_parser.print_help()
        sys.exit(1)
    return options, args

def parse_nmon_files(filename_list):
    stats_struct = {}
    start_time = host = None
    stats_data = {}
    multipath_devices = []
    last_date = None
    for filename in filename_list:
        print filename
        inputfile = open(filename, 'rb')
        csv_reader = csv.reader(inputfile, delimiter=',', quotechar='|', quoting=csv.QUOTE_NONE)
        for row in csv_reader:
            stats_type = row[0]
            interval_id = row[1]

            if stats_type == "BBBP" and row[2] == '/sbin/multipath' and len(row) > 3:
                match = re.findall('\S+ \(\S+\) (dm-\S+)', row[3])
                if match:
                    multipath_devices.append(match[0])
            if stats_type == "AAA":
                if interval_id == "host":
                    host = row[2]
            if stats_type == 'ZZZZ':
                last_interval, last_time, last_date = row[1:]
                start_time = int(last_time.split(':')[0])
            if stats_type not in stats_struct:
                stats_struct[stats_type] = row[1:]
                stats_data[stats_type] = []
            else:
                if interval_id[0] == 'T':
                    assert (last_interval == interval_id)
                    if start_time < START_HOUR or start_time >= END_HOUR:
                        continue
                    if options.date_filter and options.date_filter not in last_date:
                        continue
                    if stats_type in SHOW_FIELDS:
                        stats_data[stats_type].append((last_date, last_time, row[2:]))
                    if stats_type in ['DISKREAD', 'DISKWRITE']:
                        multipath_idxs = [stats_struct[stats_type].index(mi) for mi in multipath_devices]
                        assert(len(multipath_devices) == len(multipath_idxs))
                        total_disk = sum([float(row[2+n-1]) for n in multipath_idxs])
                        stats_data[stats_type].append((last_date, last_time, total_disk))

    return host, last_date, stats_data

def build_cpu_report(filename_list, cpu_report, disk_report, title, options):
    daily_stats = len(filename_list) == 1
    title_extra = ''
    valid_options = ["d", "h", "10m"]
    print "group by", options.group_by
    if options.group_by not in valid_options:
        options.group_by = None

    host, last_date, stats_data = parse_nmon_files(filename_list)
    if not last_date:
        return

    stats_type = 'CPU_ALL'

    sorted_data = sorted(stats_data[stats_type], key=lambda x: parser.parse(x[0]+" "+x[1]))

    if options.group_by == "10m":
        key_func = lambda x: x[0] + x[1][:4]
    elif options.group_by == "h":
        key_func = lambda x: x[0] + x[1][:2]
    else:
        key_func = lambda x: x[0]
    #print stats_data[stats_type][0][:2]


    #print sorted_data[0][0] + sorted_data[0][1][:2]
    x_values = []
    avg_usr_data = []
    avg_sys_data = []
    avg_wait_data = []

    if options.group_by is None:
        ### Full data plotting
        for start_date, start_time, g in sorted_data:
            avg_usr_data.append(float(g[0]))
            avg_sys_data.append(float(g[1]))
            avg_wait_data.append(float(g[2]))
            x_values.append(parser.parse(start_date+" "+start_time))
            title_extra = ''
    else:
        ## -g10; -gh; -gd
        for k, g in groupby(sorted_data, key=key_func):
            print "key=", k
            values = list(g)
            #pprint(values)
            if options.group_by == "10m":
                title_extra = values[0][0]
                key_str = values[0][0] + " " + values[0][1][:4] + "0"
            elif options.group_by == "h":
                key_str = values[0][0] + " " + values[0][1][:3] + "00"
            else:  # assume "date"
                title_extra = ''
                key_str = values[0][0]

            avg_usr = med([float(x[2][0]) for x in values])
            avg_sys = med([float(x[2][1]) for x in values])
            avg_wait = med([float(x[2][2]) for x in values])

            avg_usr_data.append(avg_usr)
            avg_sys_data.append(avg_sys)
            avg_wait_data.append(avg_wait)
            x_values.append(parser.parse(key_str))
            #print avg_usr, avg_sys, avg_wait

    plt.ylabel('Avg CPU -  [%s:00 - %s:00]' % (START_HOUR, END_HOUR))
    y = np.row_stack((avg_usr_data, avg_sys_data, avg_wait_data))
    y_stack = np.cumsum(y, axis=0)  # a 3x10 array

    if options.group_by == "d":
        fmt = mdates.DateFormatter('%a, %d')
        loc = mdates.DayLocator()
    elif options.group_by == "h":
        fmt = mdates.DateFormatter('%d - %H:%M')
        loc = mdates.HourLocator()
    else:
        fmt = mdates.DateFormatter('%d - %H:%M')
        loc = mdates.MinuteLocator(byminute=range(0, 60, 30))

    ax = plt.axes()
    ax.xaxis.set_major_formatter(fmt)

    ax.xaxis.set_major_locator(loc)
    fmt = '%.0f%%'
    xticks = matplotlib.ticker.FormatStrFormatter(fmt)
    ax.yaxis.set_major_formatter(xticks)

    plt.grid(True)
    fig = plt.figure(1)
    ax1 = fig.add_subplot(111)
    xn_ax = x_values
    ax1.fill_between(xn_ax, 0, y_stack[0, :], facecolor="#00FF00", alpha=.7, label='xpto')
    ax1.fill_between(xn_ax, y_stack[0, :], y_stack[1, :], facecolor="#0000FF", alpha=.7)
    ax1.fill_between(xn_ax, y_stack[1, :], y_stack[2, :], facecolor="#FF0000")
    # fig.autofmt_xdate()
    plt.setp(ax.get_xticklabels(), rotation='vertical', fontsize=8)
    plt.plot([], [], color='#00FF00', linewidth=10, label="%user")
    plt.plot([], [], color='#0000FF', linewidth=10, label="%system")
    plt.plot([], [], color='#FF0000', linewidth=10, label="%iowait")
    if options.max_y is not None:
        plt.ylim([0, float(options.max_y)])
    plt.legend()
    if daily_stats:
        title = host + " " + title_extra
    plt.title(title)
    fig.savefig(cpu_report, format='pdf', dpi=600, bbox_inches='tight')
    plt.close()


    #### Disk report
    stats_type = 'DISKREAD'
    sorted_data = sorted(stats_data[stats_type], key=key_func)
    kb_read_data = []
    x_values = []
    for k, g in groupby(sorted_data, key=key_func):
        values = list(g)
        if daily_stats:
            key_str = values[0][0] + " " + values[0][1][0:4] + "0"
        else:
            key_str = values[0][0]
        kb_read_data.append(sum([x[2] for x in values]))
        x_values.append(parser.parse(key_str))

    plt.ylabel('Total KBs/Sec -  [%s:00 - %s:00]' % (START_HOUR, END_HOUR))

    #y = np.row_stack((kb_read_data, avg_sys_data, avg_wait_data))
    #y_stack = np.cumsum(y, axis=0)  # a 3x10 array

    if daily_stats:
        fmt = mdates.DateFormatter('%H:00')
    else:
        fmt = mdates.DateFormatter('%a, %d')

    if daily_stats:
        loc = mdates.HourLocator()
    else:
        loc = mdates.DayLocator()

    ax = plt.axes()
    ax.xaxis.set_major_formatter(fmt)
    ax.xaxis.set_major_locator(loc)
    #fmt = '%.0f%%'
    #xticks = matplotlib.ticker.FormatStrFormatter(fmt)
    #ax.yaxis.set_major_formatter(xticks)

    plt.grid(True)
    fig = plt.figure(1)
    ax1 = fig.add_subplot(111)
    xn_ax = x_values
    ax1.plot(x_values, kb_read_data, label='kb_read_data')
    #ax1.fill_between(xn_ax, 0, y_stack[0, :], facecolor="#00FF00", alpha=.7, label='xpto')
    #ax1.fill_between(xn_ax, y_stack[0, :], y_stack[1, :], facecolor="#0000FF", alpha=.7)
    #ax1.fill_between(xn_ax, y_stack[1, :], y_stack[2, :], facecolor="#FF0000")
    # fig.autofmt_xdate()
    plt.setp(ax.get_xticklabels(), rotation='vertical', fontsize=8)
    plt.legend()
    if daily_stats:
        title = host + " " + last_date
    plt.title(title)
    fig.savefig(disk_report, format='pdf', dpi=300)
    plt.close()

options, args = _parse_cmd()

input_dir = args[0]
if len(args) > 1:
    mask = "*"+args[1]+"*.nmon"
else:
    mask = "*.nmon"

cpu_report = PdfPages('CPU_ALL.pdf')
disk_report = PdfPages('DISK_MULTIPATH.pdf')

# We can also set the file's metadata via the PdfPages object:

for filename in sorted(glob(join(input_dir, '*'))):
    hostname = basename(filename)
    if isdir(filename):
        print join(filename, mask)
        file_list = glob(join(filename, mask))
        build_cpu_report(file_list, cpu_report, disk_report, "2015 - " + basename(filename), options)

cpu_report.close()
disk_report.close()
