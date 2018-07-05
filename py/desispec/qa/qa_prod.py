""" Class to organize QA for a full DESI production run
"""

from __future__ import print_function, absolute_import, division

import numpy as np
import glob, os
import warnings

from desispec.io import get_exposures
from desispec.io import get_files
from desispec.io import read_meta_frame
from desispec.io import specprod_root
from desispec.io import get_nights
from .qa_multiexp import QA_MultiExp

from desiutil.log import get_logger

# log = get_logger()


class QA_Prod(QA_MultiExp):
    def __init__(self, specprod_dir=None, **kwargs):
        """ Class to organize and execute QA for a DESI production

        Args:
            specprod_dir(str): Path containing the exposures/ directory to use. If the value
                is None, then the value of :func:`specprod_root` is used instead.
        Notes:

        Attributes:
            qa_exps : list
              List of QA_Exposure classes, one per exposure in production
            data : dict
        """
        if specprod_dir is None:
            specprod_dir = specprod_root()
        self.specprod_dir = specprod_dir
        # Init
        QA_MultiExp.__init__(self, specprod_dir=specprod_dir, **kwargs)
        # Load up exposures for the full production
        nights = get_nights(specprod_dir=self.specprod_dir)
        for night in nights:
            self.mexp_dict[night] = {}
            for exposure in get_exposures(night, specprod_dir = self.specprod_dir):
                # Object only??
                frames_dict = get_files(filetype = str('frame'), night = night,
                                        expid = exposure, specprod_dir = self.specprod_dir)
                self.mexp_dict[night][exposure] = frames_dict
        # Output file names
        self.qaexp_outroot = self.qaprod_dir+'/'+self.prod_name+'_qa'


