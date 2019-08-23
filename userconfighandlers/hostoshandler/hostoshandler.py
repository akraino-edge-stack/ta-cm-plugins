#! /usr/bin/python
# Copyright 2019 Nokia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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


