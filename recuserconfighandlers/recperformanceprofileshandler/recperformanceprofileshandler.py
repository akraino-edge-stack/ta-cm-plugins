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
This plugin is used to handle REC specific performance profiles configs.
"""


class recperformanceprofileshandler(cmuserconfig.CMUserConfigPlugin):
    low_latency_options = [
        'intel_idle.max_cstate=5',
        'processor.max_cstate=5',
    ]

    def __init__(self):
        super(recperformanceprofileshandler, self).__init__()

    def handle(self, confman):
        try:
            self._set_default_type_for_provider_networks(confman)
        except configerror.ConfigError as exp:
            raise cmerror.CMError(str(exp))

    def set_low_latency_options(self, confman):
        perfprofconf = self.confman.get_performance_profiles_config_handler()
        for profile in perfprofconf.get_performance_profiles():
            perfprofconf.set_low_latency_kcmd_options(profile, self.low_latency_options)
