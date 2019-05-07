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

import os
import yaml

from cmframework.apis import cmuserconfig
from cmframework.apis import cmerror
from serviceprofiles import profiles

extra_localstoragedict = {'cephcontroller':{}}


class localstorage(cmuserconfig.CMUserConfigPlugin):
    localstorageconfdir = '/etc/opt/localstorage'

    def __init__(self):
        super(localstorage, self).__init__()
        profs = profiles.Profiles()
        allprofs = profs.get_profiles()
        self.host_group_localstoragedict = {}
        for name, prof in allprofs.iteritems():
            self.host_group_localstoragedict[name] = {}
        self.host_group_localstoragedict.update(extra_localstoragedict)

    def handle(self, confman):
        try:
            localstorageconf = confman.get_localstorage_config_handler()
            deploy_type_dir = os.path.join(self.localstorageconfdir,
                                           self._get_deployment_type(confman))
            for localstoragefile in os.listdir(deploy_type_dir):
                localstoragefilepath = os.path.join(deploy_type_dir, localstoragefile)
                localstorageconfdict = yaml.load(open(localstoragefilepath))
                logical_volumes = localstorageconfdict.get("logical_volumes", [])
                for host_group in localstorageconfdict.get("service_profiles", []):
                    if host_group not in self.host_group_localstoragedict.keys():
                        raise cmerror.CMError(
                            "%s: Not a valid host group. Check configuration in %s"
                            % (host_group, localstoragefilepath))
                    self._add_logical_volumes_to_host_group(logical_volumes, host_group)

            localstorageconf.add_localstorage(self.host_group_localstoragedict)

        except Exception as exp:
            raise cmerror.CMError(str(exp))

    def _get_deployment_type(self, confman):
        caasconf = confman.get_caas_config_handler()
        hostsconf = confman.get_hosts_config_handler()
        if caasconf.get_caas_only():
            return "caas"
        if (hostsconf.get_service_profile_hosts('controller') 
           and hostsconf.get_service_profile_hosts('caas_master')):
            return "multinode_hybrid"
        return "openstack"

    def _add_logical_volumes_to_host_group(self, lvs, host_group):
        lv_data = {lv["lvm_name"]: lv for lv in lvs}
        self.host_group_localstoragedict[host_group].update(lv_data)
