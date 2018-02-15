#!/usr/bin/env python
#
# See top-level LICENSE.rst file for Copyright information
#
# -*- coding: utf-8 -*-

"""
Interactive control of the pipeline
"""

from __future__ import absolute_import, division, print_function

import sys
import os
import argparse
import re
import glob
import subprocess

from .. import io

from .. import pipeline as pipe


class clr:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    def disable(self):
        self.HEADER = ""
        self.OKBLUE = ""
        self.OKGREEN = ""
        self.WARNING = ""
        self.FAIL = ""
        self.ENDC = ""


class PipeUI(object):

    def __init__(self):
        self.pref = "DESI"

        parser = argparse.ArgumentParser(
            description="DESI pipeline control",
            usage="""desi_pipe <command> [options]

Where supported commands are:
   create   Create a new production.
   env      Print current production location.
   update   Update an existing production.
   tasks    Get all possible tasks for a given type and states.
   check    Check the status of tasks.
   cli      Return the equivalent command line entrypoint for tasks.
   script   Generate a shell or slurm script.
   run      Generate a script and run it.
   status   Overview of production.
""")
        parser.add_argument("command", help="Subcommand to run")
        # parse_args defaults to [1:] for args, but you need to
        # exclude the rest of the args too, or validation will fail
        args = parser.parse_args(sys.argv[1:2])
        if not hasattr(self, args.command):
            print("Unrecognized command")
            parser.print_help()
            sys.exit(0)

        # Get raw data location and optionally production (if we are not
        # creating it).

        self.rawdir = io.rawdata_root()
        if args.command != "create":
            self.proddir = io.specprod_root()

        # use dispatch pattern to invoke method with same name
        getattr(self, args.command)()


    def env(self):
        print("{}{:<22} = {}{}{}".format(self.pref, "Raw data directory", clr.OKBLUE, self.rawdir, clr.ENDC))
        print("{}{:<22} = {}{}{}".format(self.pref, "Production directory", clr.OKBLUE, self.proddir, clr.ENDC))
        return


    def create(self):
        parser = argparse.ArgumentParser(description="Create a new production")

        parser.add_argument("--redux", required=False, default=None,
            help="value to use for DESI_SPECTRO_REDUX")

        parser.add_argument("--prod", required=False, default=None,
            help="value to use for SPECPROD")

        parser.add_argument("--nside", required=False, type=int, default=64,
            help="HEALPix nside value to use for spectral grouping.")

        args = parser.parse_args(sys.argv[2:])

        # Check production name

        prodname = None
        if "SPECPROD" in os.environ:
            prodname = os.environ["SPECPROD"]
        else:
            prodname = args.prod
            if prodname is None:
                print("You must set SPECPROD in your environment or use the "
                    "--prod commandline option")
                sys.exit(0)
            os.environ["SPECPROD"] = prodname

        # Check spectro redux location

        proddir = None
        if "DESI_SPECTRO_REDUX" in os.environ:
            specdir = os.environ["DESI_SPECTRO_REDUX"]
            proddir = os.path.join(specdir, prodname)
        else:
            specdir = args.redux
            if specdir is None:
                print("You must set DESI_SPECTRO_REDUX in your environment or "
                    "use the --redux commandline option")
                sys.exit(0)
            specdir = os.path.abspath(specdir)
            proddir = os.path.join(specdir, prodname)
            os.environ["DESI_SPECTRO_REDUX"] = specdir

        pipe.update_prod(nightstr=None, hpxnside=args.nside)

        # create setup shell snippet

        setupfile = os.path.abspath(os.path.join(proddir, "setup.sh"))
        with open(setupfile, "w") as s:
            s.write("# Generated by desi_pipe\n")
            s.write("export DESI_SPECTRO_DATA={}\n".format(self.rawdir))
            s.write("export DESI_SPECTRO_REDUX={}\n".format(specdir))
            s.write("export SPECPROD={}\n".format(prodname))
            s.write("\n")
            s.write("#export DESI_LOGLEVEL=\"DEBUG\"\n\n")

        return


    def update(self):
        parser = argparse.ArgumentParser(description="Update a production")

        parser.add_argument("--nights", required=False, default=None,
            help="comma separated (YYYYMMDD) or regex pattern- only nights "
            "matching these patterns will be examined.")

        parser.add_argument("--nside", required=False, type=int, default=64,
            help="HEALPix nside value to use for spectral grouping.")

        args = parser.parse_args(sys.argv[2:])

        pipe.update_prod(nightstr=args.nights, hpxnside=args.nside)

        return


    def tasks(self):
        availtypes = ",".join(pipe.db.task_types())

        parser = argparse.ArgumentParser(description="Get all tasks of a "
            "particular type for one or more nights")

        parser.add_argument("--tasktype", required=True, default=None,
            help="task type ({})".format(availtypes))

        parser.add_argument("--nights", required=False, default=None,
            help="comma separated (YYYYMMDD) or regex pattern- only nights "
            "matching these patterns will be examined.")

        parser.add_argument("--states", required=False, default=None,
            help="comma separated list of states (see defs.py).  Only tasks "
            "in these states will be returned.")

        parser.add_argument("--taskfile", required=False, default=None,
            help="write tasks to this file (if not specified, write to STDOUT)")

        args = parser.parse_args(sys.argv[2:])

        states = None
        if args.states is None:
            states = pipe.task_states
        else:
            states = args.states.split(",")
            for s in states:
                if s not in pipe.task_states:
                    print("Task state '{}' is not valid".format(s))
                    sys.exit(0)

        dbpath = os.path.join(self.proddir, pipe.prod_db_name)
        db = pipe.db.DataBase(dbpath, "r")

        allnights = io.get_nights(strip_path=True)
        nights = pipe.prod.select_nights(allnights, args.nights)
        ntlist = ",".join(nights)

        tasks = list()
        with db.conn as con:
            cur = con.cursor()
            cur.execute(\
                "select name, state from {} where night in ({})"\
                    .format(args.tasktype, ntlist))
            tasks = [ x for (x, y) in cur.fetchall() if \
                pipe.task_int_to_state[y] in states ]

        pipe.prod.task_write(args.taskfile, tasks)

        return


    def check(self):
        parser = argparse.ArgumentParser(description="Check the state of "
            "pipeline tasks")

        parser.add_argument("--taskfile", required=False, default=None,
            help="read tasks from this file (if not specified, read from "
            "STDIN)")

        parser.add_argument("--nodb", required=False, default=False,
            action="store_true", help="Do not use the production database.")

        args = parser.parse_args(sys.argv[2:])

        tasks = pipe.prod.task_read(args.taskfile)

        db = None
        if not args.nodb:
            dbpath = os.path.join(self.proddir, pipe.prod_db_name)
            db = pipe.db.DataBase(dbpath, "r")

        states = pipe.db.check_tasks(tasks, db=db)

        for tsk in tasks:
            print("{} : {}".format(tsk, states[tsk]))
        sys.stdout.flush()

        return


    def _parse_run_opts(self, parser):
        """Internal function to parse options for running.

        This provides a consistent set of run-time otpions for the
        "dryrun", "script", and "run" commands.

        """
        availtypes = ",".join(pipe.db.task_types())
        scrdir = io.get_pipe_scriptdir()

        parser.add_argument("--tasktype", required=True, default=None,
            help="task type ({})".format(availtypes))

        parser.add_argument("--taskfile", required=False, default=None,
            help="read tasks from this file (if not specified, read from "
            "STDIN)")

        parser.add_argument("--nersc", required=False, default=None,
            help="write a script for this NERSC system (edison | cori-haswell "
            "| cori-knl)")

        parser.add_argument("--nersc_queue", required=False, default="regular",
            help="write a script for this NERSC queue (debug | regular)")

        parser.add_argument("--nersc_runtime", required=False, type=int,
            default=30, help="Then maximum run time (in minutes) for a single "
            " job.  If the list of tasks cannot be run in this time, multiple "
            " job scripts will be written")

        parser.add_argument("--nersc_shifter", required=False, default=None,
            help="The shifter image to use for NERSC jobs")

        parser.add_argument("--mpi_procs", required=False, type=int, default=1,
            help="The number of MPI processes to use for non-NERSC shell "
            "scripts (default 1)")

        parser.add_argument("--mpi_run", required=False, type=str,
            default="mpirun -np", help="The command to launch MPI programs "
            "for non-NERSC shell scripts (default do not use MPI)")

        parser.add_argument("--procs_per_node", required=False, type=int,
            default=0, help="The number of processes to use per node.  If not "
            "specified it uses a default value for each machine.")

        parser.add_argument("--outdir", required=False, default=scrdir,
            help="put scripts and logs in this directory relative to the "
            "production 'run' directory.")

        parser.add_argument("--nodb", required=False, default=False,
            action="store_true", help="Do not use the production database.")

        parser.add_argument("--debug", required=False, default=False,
            action="store_true", help="debugging messages in job logs")

        args = parser.parse_args(sys.argv[2:])

        return args


    def dryrun(self):

        parser = argparse.ArgumentParser(description="Print equivalent "
            "command-line jobs that would be run given the tasks and total"
            "number of processes")

        args = self._parse_run_opts(parser)

        tasks = pipe.prod.task_read(args.taskfile)

        (db, opts) = pipe.prod.load_prod("r")
        if args.nodb:
            db = None

        ppn = args.procs_per_node

        if args.nersc is None:
            # Not running at NERSC
            if ppn <= 0:
                ppn = args.mpi_procs
            pipe.run.dry_run(args.tasktype, tasks, opts, args.mpi_procs,
                ppn, db=db, launch="mpirun -n", force=False)
        else:
            # Running at NERSC
            hostprops = pipe.scriptgen.nersc_machine(args.nersc,
                args.nersc_queue)
            if ppn <= 0:
                ppn = hostprops["nodecores"]

            joblist = pipe.scriptgen.nersc_job_size(args.tasktype, tasks,
                args.nersc, args.nersc_queue, args.nersc_runtime, nodeprocs=ppn,
                db=db)

            launch="srun -n"
            for (jobnodes, jobtasks) in joblist:
                jobprocs = jobnodes * ppn
                pipe.run.dry_run(args.tasktype, jobtasks, opts, jobprocs,
                    ppn, db=db, launch=launch, force=False)

        return


    def script(self):
        availtypes = ",".join(pipe.db.task_types())

        parser = argparse.ArgumentParser(description="Create a batch script "
            "for the list of tasks.  If the --nersc option is not given, "
            "create a shell script that optionally uses mpirun.")

        args = self._parse_run_opts(parser)

        proddir = os.path.abspath(io.specprod_root())

        tasks = pipe.prod.task_read(args.taskfile)

        outsubdir = args.outdir

        outdir = os.path.join(proddir, io.get_pipe_rundir(), outsubdir)

        mstr = "shell"
        if args.nersc is not None:
            mstr = args.nersc

        outstr = "{}_{}".format(args.tasktype, mstr)
        outscript = os.path.join(outdir, outstr)
        outlog = os.path.join(outdir, outstr)

        (db, opts) = pipe.prod.load_prod("r")
        if args.nodb:
            db = None

        ppn = args.procs_per_node

        # FIXME: Add openmp / multiproc function to task classes and
        # call them here.

        if args.nersc is None:
            # Not running at NERSC
            pipe.scriptgen.batch_shell(args.tasktype, tasks, outscript, outlog,
                mpirun=args.mpi_run, mpiprocs=args.mpi_procs, openmp=1, db=None)

        else:
            # Running at NERSC
            if ppn <= 0:
                hostprops = pipe.scriptgen.nersc_machine(args.nersc,
                    args.nersc_queue)
                ppn = hostprops["nodecores"]

            pipe.scriptgen.batch_nersc(args.tasktype, tasks, outscript, outlog,
                args.tasktype, args.nersc, args.nersc_queue, args.nersc_runtime,
                nodeprocs=ppn, openmp=False, multiproc=False, db=db,
                                       shifterimg=args.shifterimg,debug=args.debug)

        return


    def run(self):
        # This will call the script generation and then actually submit
        # the job(s), returning the job ID to the command line.
        pass


    def status(self):
        # This will be an improved version of the old desi_pipe_status.
        pass








    #
    # def all(self):
    #     self.load_state()
    #     # go through the current state and accumulate success / failure
    #     status = {}
    #     for st in pipe.step_types:
    #         status[st] = {}
    #         status[st]["total"] = 0
    #         status[st]["none"] = 0
    #         status[st]["running"] = 0
    #         status[st]["fail"] = 0
    #         status[st]["done"] = 0
    #
    #     fts = pipe.file_types_step
    #     for name, nd in self.grph.items():
    #         tp = nd["type"]
    #         if tp in fts.keys():
    #             status[fts[tp]]["total"] += 1
    #             status[fts[tp]][nd["state"]] += 1
    #
    #     for st in pipe.step_types:
    #         beg = ""
    #         if status[st]["done"] == status[st]["total"]:
    #             beg = clr.OKGREEN
    #         elif status[st]["fail"] > 0:
    #             beg = clr.FAIL
    #         elif status[st]["running"] > 0:
    #             beg = clr.WARNING
    #         print("{}    {}{:<12}{} {:>5} tasks".format(self.pref, beg, st, clr.ENDC, status[st]["total"]))
    #     print("")
    #     return
    #
    #
    # def step(self):
    #     parser = argparse.ArgumentParser(description="Details about a particular pipeline step")
    #     parser.add_argument("step", help="Step name (allowed values are: bootcalib, specex, psfcombine, extract, fiberflat, sky, stdstars, fluxcal, procexp, and zfind).")
    #     parser.add_argument("--state", required=False, default=None, help="Only list tasks in this state (allowed values are: done, fail, running, none)")
    #     # now that we"re inside a subcommand, ignore the first
    #     # TWO argvs
    #     args = parser.parse_args(sys.argv[2:])
    #
    #     if args.step not in pipe.step_types:
    #         print("Unrecognized step name")
    #         parser.print_help()
    #         sys.exit(0)
    #
    #     self.load_state()
    #
    #     tasks_done = []
    #     tasks_none = []
    #     tasks_fail = []
    #     tasks_running = []
    #
    #     fts = pipe.step_file_types[args.step]
    #     for name, nd in self.grph.items():
    #         tp = nd["type"]
    #         if tp == fts:
    #             stat = nd["state"]
    #             if stat == "done":
    #                 tasks_done.append(name)
    #             elif stat == "fail":
    #                 tasks_fail.append(name)
    #             elif stat == "running":
    #                 tasks_running.append(name)
    #             else:
    #                 tasks_none.append(name)
    #
    #     if (args.state is None) or (args.state == "done"):
    #         for tsk in sorted(tasks_done):
    #             print("{}    {}{:<20}{}".format(self.pref, clr.OKGREEN, tsk, clr.ENDC))
    #     if (args.state is None) or (args.state == "fail"):
    #         for tsk in sorted(tasks_fail):
    #             print("{}    {}{:<20}{}".format(self.pref, clr.FAIL, tsk, clr.ENDC))
    #     if (args.state is None) or (args.state == "running"):
    #         for tsk in sorted(tasks_running):
    #             print("{}    {}{:<20}{}".format(self.pref, clr.WARNING, tsk, clr.ENDC))
    #     if (args.state is None) or (args.state == "none"):
    #         for tsk in sorted(tasks_none):
    #             print("{}    {:<20}".format(self.pref, tsk))
    #
    #
    # def task(self):
    #     parser = argparse.ArgumentParser(description="Details about a specific pipeline task")
    #     parser.add_argument("task", help="Task name (as displayed by the \"step\" command).")
    #     parser.add_argument("--log", required=False, default=False, action="store_true", help="Print the log and traceback, if applicable")
    #     parser.add_argument("--retry", required=False, default=False, action="store_true", help="Retry the specified task")
    #     parser.add_argument("--opts", required=False, default=None, help="Retry using this options file")
    #     # now that we're inside a subcommand, ignore the first
    #     # TWO argvs
    #     args = parser.parse_args(sys.argv[2:])
    #
    #     self.load_state()
    #
    #     if args.task not in self.grph.keys():
    #         print("Task {} not found in graph.".format(args.task))
    #         sys.exit(0)
    #
    #     nd = self.grph[args.task]
    #     stat = nd["state"]
    #
    #     beg = ""
    #     if stat == "done":
    #         beg = clr.OKGREEN
    #     elif stat == "fail":
    #         beg = clr.FAIL
    #     elif stat == "running":
    #         beg = clr.WARNING
    #
    #     filepath = pipe.graph_path(args.task)
    #
    #     (night, gname) = pipe.graph_night_split(args.task)
    #     nfaildir = os.path.join(self.faildir, night)
    #     nlogdir = os.path.join(self.logdir, night)
    #
    #     logpath = os.path.join(nlogdir, "{}.log".format(gname))
    #
    #     ymlpath = os.path.join(nfaildir, "{}_{}.yaml".format(pipe.file_types_step[nd["type"]], args.task))
    #
    #     if args.retry:
    #         if stat != "fail":
    #             print("Task {} has not failed, cannot retry".format(args.task))
    #         else:
    #             if os.path.isfile(ymlpath):
    #                 newopts = None
    #                 if args.opts is not None:
    #                     newopts = pipe.yaml_read(args.opts)
    #                 try:
    #                     pipe.retry_task(ymlpath, newopts=newopts)
    #                 finally:
    #                     self.grph[args.task]["state"] = "done"
    #                     pipe.graph_db_write(self.grph)
    #             else:
    #                 print("Failure yaml dump does not exist!")
    #     else:
    #         print("{}{}:".format(self.pref, args.task))
    #         print("{}    state = {}{}{}".format(self.pref, beg, stat, clr.ENDC))
    #         print("{}    path = {}".format(self.pref, filepath))
    #         print("{}    logfile = {}".format(self.pref, logpath))
    #         print("{}    inputs required:".format(self.pref))
    #         for d in sorted(nd["in"]):
    #             print("{}      {}".format(self.pref, d))
    #         print("{}    output dependents:".format(self.pref))
    #         for d in sorted(nd["out"]):
    #             print("{}      {}".format(self.pref, d))
    #         print("")
    #
    #         if args.log:
    #             print("=========== Begin Log =============")
    #             print("")
    #             with open(logpath, "r") as f:
    #                 logdata = f.read()
    #                 print(logdata)
    #             print("")
    #             print("============ End Log ==============")
    #             print("")
    #
    #     return


def main():
    p = PipeUI()
