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

#pylint: disable=missing-docstring,invalid-name,too-few-public-methods
import os
import json
import string
from jinja2 import Environment
from cmframework.apis import cmansibleinventoryconfig
from cmframework.apis import cmerror
from cmdatahandlers.api import configerror
import hw_detector.hw_detect_lib as hw

JSON_HW_HOST_VAR = """
{
    {% for host in hosts %}
    "{{ host.name }}": {
         "vendor": "{{ host.vendor }}",
         "product_family": "{{ host.product_family }}",
         "mgmt_mac": "{{ host.mgmt_mac }}"
    } {% if not loop.last %},{% endif %}
    {% endfor %}
}
"""
class Host(object):
    def __init__(self, name):
        self.name = name
        self.vendor = None
        self.product_family = None

class hwinventory(cmansibleinventoryconfig.CMAnsibleInventoryConfigPlugin):
    def __init__(self, confman, inventory, ownhost):
        super(hwinventory, self).__init__(confman, inventory, ownhost)
        self.host_objects = []
        self._hosts_config_handler = self.confman.get_hosts_config_handler()

    def handle_bootstrapping(self):
	self.handle()

    def handle_provisioning(self):
	self.handle()

    def handle_setup(self):
        pass

    def handle_postconfig(self):
	self.handle()

    def handle(self):
        self._set_hw_types()
        self._add_hw_config()

    
    def _add_hw_config(self):
        try:
            text = Environment().from_string(JSON_HW_HOST_VAR).render(
                hosts=self.host_objects)
            inventory = json.loads(text)
            self.add_global_var("hw_inventory_details", inventory)
#            for host in inventory.keys():
#                for var, value in inventory[host].iteritems():
#                    self.add_host_var(host, var, value)
        except Exception as exp:
            raise cmerror.CMError(str(exp))

    def _get_hw_type_of_host(self, name):
        hwmgmt_addr = self._hosts_config_handler.get_hwmgmt_ip(name)
        hwmgmt_user = self._hosts_config_handler.get_hwmgmt_user(name)
        hwmgmt_pass = self._hosts_config_handler.get_hwmgmt_password(name)
        return hw.get_hw_data(hwmgmt_addr, hwmgmt_user, hwmgmt_pass)
        
    def _set_hw_types(self):
        hosts = self._hosts_config_handler.get_hosts()
        for host in hosts:
            host_object = Host(host)
            hw_details = self._get_hw_type_of_host(host)
            host_object.vendor = hw_details.get("vendor", "Unknown")
            host_object.product_family = hw_details.get("product_family", "Unknown")
            host_object.mgmt_mac = hw_details.get('info', {}).get("MAC Address", "00:00:00:00:00:00")
            self.host_objects.append(host_object) 
