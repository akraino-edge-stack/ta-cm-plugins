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
from serviceprofiles import profiles

import os
import re

"""
This plugin is used to setup OVS defaults
"""
class ovshandler(cmuserconfig.CMUserConfigPlugin):
    def __init__(self):
        super(ovshandler,self).__init__()

    def handle(self, confman):
        try:
            hostsconf = confman.get_hosts_config_handler()
            netconf = confman.get_networking_config_handler()

            hosts = hostsconf.get_hosts()
            for host in hosts:
                node_service_profiles = hostsconf.get_service_profiles(host)
                for profile in node_service_profiles:
                    if profile == profiles.Profiles.get_compute_service_profile():
                        netconf.add_ovs_config_defaults(host)
        except Exception as exp:
            raise cmerror.CMError(str(exp))
