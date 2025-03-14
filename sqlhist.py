#!/usr/bin/env python3
"""
sqlhist: manage bash sqlite3 command line history

desc:
  importsql: import from cmdhist format bash log files
  showdups: show command_id of all duplicate rows
  dedup: remove all duplicate rows, leaves command_id holes

"""
__url__     = 'https://github.com/smemsh/utilmisc/'
__author__  = 'Scott Mcdermott <scott@smemsh.net>'
__license__ = 'GPL-2.0'

from sys import exit, hexversion
if hexversion < 0x030d00f0: exit("minpython: %s" % hexversion)

from sys import argv, stdin, stdout, stderr
from time import strftime, strptime
from select import select
from traceback import print_exc

from os.path import basename
from os import (
    getenv, unsetenv,
    isatty, dup,
    close as osclose,
    EX_OK as EXIT_SUCCESS,
    EX_SOFTWARE as EXIT_FAILURE,
)

import sqlite3
from collections import namedtuple

###

table = 'command_lines'
timefmt = getenv('HISTTIMEFORMAT').rstrip()

# order of fields in cmdhist format.  splits on whitespace, with
# exception of last field (which can contain arbitrary whitespace)
#
fields = [
    'hostname',
    'start_time_t',
    'end_time_t',
    'duration_secs',
    'ttytype_code_id',
    'ttynum',
    'shlvl',
    'ret',
    'command',
]
cleaves = len(fields) - 1

# select a subset representing all but first duplicate row
# see https://www.sqlite.org/windowfunctions.html
#
where_nonunique_ids = f"""
    WHERE command_id
    IN (
        SELECT command_id
        FROM (
            SELECT command_id, ROW_NUMBER()
            OVER (
                PARTITION BY {','.join(fields)}
                ORDER BY command_id
            )
            AS rownum
            FROM command_lines
        )
        WHERE rownum > 1
    )
"""

###

def err(*args, **kwargs):
    print(*args, file=stderr, **kwargs)

def bomb(*args, **kwargs):
    err(*args, **kwargs)
    exit(EXIT_FAILURE)

###

def showdups():
    sql = f"SELECT command_id FROM {table} {where_nonunique_ids}"
    for row in cur.execute(sql):
        print(row[0])

def dedup():
    sql = f"DELETE FROM {table} {where_nonunique_ids}"
    cur.execute(sql)
    db.commit()

def importsql():
    linenum = 0
    for line in infile:
        linenum += 1
        clidata = line.rstrip().split(maxsplit=cleaves)
        try:
            cmd = namedtuple('Command', fields)(*clidata)
            for var in ['start_time_t', 'end_time_t']:
                time_t = strftime("%s", strptime(getattr(cmd, var), timefmt))
                cmd = cmd._replace(**{var: time_t})
        except (TypeError, ValueError):
            print(f"bad: {linenum}")
            continue

        sql = f"""
            INSERT INTO {table} ({','.join(fields)})
            VALUES ({','.join([f':{field}' for field in fields])})
        """
        cur.execute(sql, cmd._asdict())

    db.commit()

###

def main():

    if debug == 1:
        breakpoint()

    try: subprogram = globals()[invname]
    except (KeyError, TypeError):
        from inspect import trace
        if len(trace()) == 1: bomb("unimplemented")
        else: raise

    return subprogram()

###

if __name__ == "__main__":

    invname = basename(argv[0])
    args = argv[1:]

    # move stdin, pdb needs stdio fds itself
    stdinfd = stdin.fileno()
    if not isatty(stdinfd) and select([stdin], [], [])[0]:
        infile = open(dup(stdinfd))
        osclose(stdinfd)  # cpython bug 73582
        try: stdin = open('/dev/tty')
        except: pass  # no ctty, but then pdb would not be in use
    else:
        if invname == 'importsql':
            bomb("must supply input on stdin")
        else: pass

    from bdb import BdbQuit
    if debug := int(getenv('DEBUG') or 0):
        import pdb
        from pprint import pp
        err('debug: enabled')
        unsetenv('DEBUG')  # otherwise forked children hang

    try:
        db = sqlite3.connect(getenv("LOGFILE_SQL"))
        db.set_trace_callback(print if debug == 3 else None)
        sqlite3.enable_callback_tracebacks(True)
        cur = db.cursor()
    except:
        print_exc(file=stderr)
        bomb("failed to properly open the sqlite3 database")

    try: main()
    except BdbQuit: bomb("debug: stop")
    except SystemExit: raise
    except KeyboardInterrupt: bomb("interrupted")
    except:
        print_exc(file=stderr)
        if debug: pdb.post_mortem()
        else: bomb("aborting...")
    finally:  # cpython bug 55589
        try: stdout.flush()
        finally:
            try: stdout.close()
            finally:
                try: stderr.flush()
                except: pass
                finally: stderr.close()
