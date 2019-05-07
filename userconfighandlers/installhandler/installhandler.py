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

import netifaces as ni
from cmframework.apis import cmuserconfig
from cmframework.apis import cmerror
from cmdatahandlers.api import configerror
from cmdatahandlers.api import utils
"""
This plugin is used to define the installation node in the system
"""
class installhandler(cmuserconfig.CMUserConfigPlugin):
    def __init__(self):
        super(installhandler,self).__init__()

    def handle(self, confman):
        try:
            hostsconf = confman.get_hosts_config_handler()
            hostname = 'controller-1'
            if not utils.is_virtualized():
                ownip = utils.get_own_hwmgmt_ip()
                hostname = hostsconf.get_host_having_hwmgmt_address(ownip)
            else:
                mgmt_addr = {}

                for host in hostsconf.get_hosts():
                    try:
                        mgmt_addr[host] = hostsconf.get_mgmt_mac(host)[0]
                    except IndexError:
                        pass
                for interface in ni.interfaces():
                    a = ni.ifaddresses(interface)
                    mac_list = []
                    for mac in a[ni.AF_LINK]:
                        mac_list.append(mac.get('addr', None))
                    for host, mgmt_mac in mgmt_addr.iteritems():
                        if mgmt_mac in mac_list:
                            hostsconf.set_installation_host(host)
                            return

            hostsconf.set_installation_host(hostname)
        except configerror.ConfigError as exp:
            raise cmerror.CMError(str(exp))
