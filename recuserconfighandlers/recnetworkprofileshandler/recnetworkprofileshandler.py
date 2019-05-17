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
from cmdatahandlers.network_profiles.config import MissingSriovProviderNetworks

"""
This plugin is used to add IP addresses for all the host(s) that are defined in
the user configuration. The IP addresses will be allocated in the hosts
according to which networks are actually used in the host.
It also takes care of allocating the ipmit console port and vbmc ports.
"""


class recnetworkprofileshandler(cmuserconfig.CMUserConfigPlugin):
    defaul_sriov_net_type = 'caas'

    def __init__(self):
        super(recnetworkprofileshandler, self).__init__()

    def handle(self, confman):
        try:
            self._set_default_sriov_provider_network_type(confman)
        except configerror.ConfigError as exp:
            raise cmerror.CMError(str(exp))

    def _set_default_sriov_provider_network_type(self, confman):
        netprofconf = confman.get_network_profiles_config_handler()
        network_profiles = netprofconf.get_network_profiles()
        for profile in network_profiles:
            try:
                for sriov_net in netprofconf.get_profile_sriov_provider_networks(profile):
                    if not netprofconf.get_profile_sriov_provider_network_type(
                            profile, sriov_net):
                        netprofconf.set_profile_sriov_provider_network_type(
                                profile, sriov_net, self.defaul_sriov_net_type)
            except MissingSriovProviderNetworks:
                pass
