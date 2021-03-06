"""
lvmspec.io.qa
===============

IO routines for QA
"""
from __future__ import print_function, absolute_import, division

import os, yaml
import json

from lvmutil.io import yamlify

from lvmspec.io import findfile
from lvmspec.io.util import makepath
from lvmutil.log import get_logger
# log=get_logger()


def read_qa_data(filename):
    """Read data from a QA file
    """
    # Read yaml
    with open(filename, 'r') as infile:
        qa_data = yaml.load(infile)
    # Return
    return qa_data


def read_qa_brick(filename):
    """Generate a QA_Brick object from a data file
    """
    from lvmspec.qa.qa_brick import QA_Brick
    # Read
    qa_data = read_qa_data(filename)

    # Instantiate
    qabrick = QA_Brick(in_data=qa_data)

    return qabrick


def read_qa_frame(filename):
    """Generate a QA_Frame object from a data file
    """
    from lvmspec.qa.qa_frame import QA_Frame
    #- check if filename is (night, expid, camera) tuple instead
    if not isinstance(filename, str):
        night, expid, camera = filename
        filename = findfile('qa', night, expid, camera)

    # Read
    qa_data = read_qa_data(filename)

    # Instantiate
    qaframe = QA_Frame(qa_data)

    return qaframe


def load_qa_frame(filename, frame=None, flavor=None):
    """ Load an existing QA_Frame or generate one, as needed

    Args:
        filename: str
        frame: Frame object, optional
        flavor: str, optional
            Type of QA_Frame

    Returns:
        qa_frame: QA_Frame object
    """
    from lvmspec.qa.qa_frame import QA_Frame
    log=get_logger()
    if os.path.isfile(filename): # Read from file, if it exists
        qaframe = read_qa_frame(filename)
        log.info("Loaded QA file {:s}".format(filename))
        # Check against frame, if provided
        if frame is not None:
            for key in ['camera','expid','night','flavor']:
                assert getattr(qaframe, key) == frame.meta[key.upper()]
    else:  # Init
        if frame is None:
            log.error("QA file {:s} does not exist.  Expecting frame input".format(filename))
        qaframe = QA_Frame(frame)
    # Set flavor?
    if flavor is not None:
        qaframe.flavor = flavor
    # Return
    return qaframe


def load_qa_brick(filename):
    """ Load an existing QA_Brick or generate one, as needed
    Args:
        filename: str

    Returns:
    qa_brick: QA_Brick object
    """
    from lvmspec.qa.qa_brick import QA_Brick
    log=get_logger()
    if os.path.isfile(filename): # Read from file, if it exists
        qabrick = read_qa_brick(filename)
        log.info("Loaded QA file {:s}".format(filename))
    else:  # Init
        qabrick = QA_Brick()
    # Return
    return qabrick

def write_qa_brick(outfile, qabrick):
    """Write QA for a given exposure

    Args:
        outfile : filename
        qabrick : QA_Brick object
            _data: dict of QA info
    """
    outfile = makepath(outfile, 'qa')

    # Simple yaml
    ydict = yamlify(qabrick.data)
    with open(outfile, 'w') as yamlf:
        yamlf.write( yaml.dump(ydict))#, default_flow_style=True) )

    return outfile


def write_qa_frame(outfile, qaframe, verbose=False):
    """Write QA for a given frame

    Args:
        outfile : str
          filename
        qa_exp : QA_Frame object, with the following attributes
            qa_data: dict of QA info
    """
    log=get_logger()
    outfile = makepath(outfile, 'qa')

    # Generate the dict
    odict = {qaframe.night: {qaframe.expid: {qaframe.camera: {}, 'flavor': qaframe.flavor}}}
    odict[qaframe.night][qaframe.expid][qaframe.camera] = qaframe.qa_data
    ydict = yamlify(odict)
    # Simple yaml
    with open(outfile, 'w') as yamlf:
        yamlf.write( yaml.dump(ydict))#, default_flow_style=True) )
    if verbose:
        log.info("Wrote QA frame file: {:s}".format(outfile))

    return outfile


def write_qa_exposure(outroot, qaexp, ret_dict=False):
    """Write QA for a given exposure

    Args:
        outroot : str
          filename without format extension
        qa_exp : QA_Exposure object
        ret_dict : bool, optional
          Return dict only?  [for qa_prod, mainly]
    Returns:
        outfile or odict : str or dict
    """
    # Generate the dict
    odict = {qaexp.night: {qaexp.expid: {}}}
    odict[qaexp.night][qaexp.expid]['flavor'] = qaexp.flavor
    odict[qaexp.night][qaexp.expid]['meta'] = qaexp.meta
    cameras = list(qaexp.data['frames'].keys())
    for camera in cameras:
        odict[qaexp.night][qaexp.expid][camera] = qaexp.data['frames'][camera]
    # Return dict only?
    if ret_dict:
        return odict
    # Simple yaml
    ydict = yamlify(odict)
    outfile = outroot+'.yaml'
    outfile = makepath(outfile, 'qa')
    with open(outfile, 'w') as yamlf:
        yamlf.write( yaml.dump(ydict))#, default_flow_style=True) )

    return outfile


def load_qa_prod(inroot):
    """Load QA for a given production

    Args:
        inroot : str
          filename without format extension
    Returns:
        odict : dict
    """
    log=get_logger()
    infile = inroot+'.json'
    log.info("Loading QA prod file: {:s}".format(infile))
    # Read
    if not os.path.exists(infile):
        log.info("QA prod file {:s} does not exist!".format(infile))
        log.error("You probably need to generate it with desi_qa_prod --make_frameqa=3 --slurp")
    with open(infile, 'rt') as fh:
        odict = json.load(fh)
    # Return
    return odict


def write_qa_prod(outroot, qaprod, indent=True):
    """Write QA for a given production

    Args:
        outroot : str
          filename without format extension
        qa_prod : QA_Prod object

    Returns:
        outfile: str
          output filename
    """
    from lvmutil.io import combine_dicts
    log=get_logger()
    outfile = outroot+'.json'
    outfile = makepath(outfile, 'qa')

    # Loop on exposures
    odict = {}
    for qaexp in qaprod.qa_exps:
        # Get the exposure dict
        idict = write_qa_exposure('foo', qaexp, ret_dict=True)
        odict = combine_dicts(odict, idict)
    ydict = yamlify(odict)  # This works well for JSON too
    # Simple json
    with open(outfile, 'wt') as fh:
        json.dump(ydict, fh, indent=indent)
    log.info('Wrote QA_Prod file: {:s}'.format(outfile))

    return outfile


def write_qa_ql(outfile, qaresult):
    """Write QL output files

       Args:
           outfile : str
             filename to be written (yaml)
           qaresult : dict
             QAresults from run_qa()

       Returns:
           outfile : str
    """
    import yaml
    from lvmutil.io import yamlify
    # Take in QL input and output to yaml
    qadict = yamlify(qaresult)
    f=open(outfile,"w")
    f.write(yaml.dump(qadict))
    return outfile


