# Copyright (C) 2019 Nokia
# All rights reserved

from nokia.cmframework.apis import cmuserconfig
from nokia.cmframework.apis import cmerror
from nokia.cmdatautils.api import configerror

import os
import re

"""

"""
class hostoshandler(cmuserconfig.CMUserConfigPlugin):
    def __init__(self):
        super(hostoshandler,self).__init__()

    def handle(self, confman):
        try:
            hostosconf = confman.get_host_os_config_handler()
            hostosconf.add_defaults()

        except Exception as exp:
            raise cmerror.CMError(str(exp))


