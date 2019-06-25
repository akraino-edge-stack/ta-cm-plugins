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
This plugin is used to handle REC specific infra logging configs. Currently
its sole purpose is to set the default plugin (elasticsearch) for internal logging.
"""


class reccaashandler(cmuserconfig.CMUserConfigPlugin):

    def __init__(self):
        super(reccaashandler, self).__init__()

    def handle(self, confman):
        try:
            self._set_default_infra_log_store(confman)
        except configerror.ConfigError as exp:
            raise cmerror.CMError(str(exp))

    @staticmethod
    def _set_default_infra_log_store(confman):
        root = 'cloud.caas'
        log_conf = confman.get_caas_handler()
        if not log_conf.get_caas_parameter('infra_log_store'):
            log_conf.config[root]['infra_log_store'] = 'elasticsearch'
