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

from cmframework.apis import cmuserconfig
from cmframework.apis import cmerror
from cmdatahandlers.api import configerror

"""
This plugin is used to add default values for auth_type and serverkeys_path parameters in user_config
if they are not present
"""
class timehandler(cmuserconfig.CMUserConfigPlugin):
    def __init__(self):
        super(timehandler, self).__init__()

    def handle(self, confman):
        try:
            timeconf = confman.get_time_config_handler()
            ROOT = 'cloud.time'
            if 'auth_type' not in timeconf.config[ROOT]:
                timeconf.config[ROOT]['auth_type'] = 'none'
            if 'serverkeys_path' not in timeconf.config[ROOT]:
                timeconf.config[ROOT]['serverkeys_path'] = ''
        except configerror.ConfigError as exp:
            raise cmerror.CMError(str(exp))
