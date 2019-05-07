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
This plugin is used to add IP addresses for all the host(s) that are defined in 
the user configuration. The IP addresses will be allocated in the hosts 
according to which networks are actually used in the host.
It also takes care of allocating the ipmit console port and vbmc ports.
"""
class iphandler(cmuserconfig.CMUserConfigPlugin):
    def __init__(self):
        super(iphandler,self).__init__()

    def handle(self, confman):
        try:
            hostsconf = confman.get_hosts_config_handler()
            netconf = confman.get_networking_config_handler()
            hosts = hostsconf.get_hosts()
            installation_host = hostsconf.get_installation_host()
            # Installation host has to be the first one in the list
            # this so that the IP address of the installation host
            # does not change during the deployment.
            hosts.remove(installation_host)
            hosts.insert(0, installation_host)
            for host in hosts:
                netconf.add_host_networks(host)
                hostsconf.add_vbmc_port(host)
                hostsconf.add_ipmi_terminal_port(host)
            # add the vip(s)
            netconf.add_external_vip()
            netconf.add_internal_vip()
        except configerror.ConfigError as exp:
            raise cmerror.CMError(str(exp))
