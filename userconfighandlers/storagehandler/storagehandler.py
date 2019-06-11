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


class storagehandler(cmuserconfig.CMUserConfigPlugin):

    def __init__(self):
        super(storagehandler, self).__init__()
        self.hosts_config_handler = None
        self.storage_config_handler = None
        self.openstack_config_handler = None

    @property
    def _managements(self):
        return self.hosts_config_handler.get_service_profile_hosts('management')

    @property
    def _storages(self):
        return self.hosts_config_handler.get_service_profile_hosts('storage')

    @property
    def _backend(self):
        return self.openstack_config_handler.get_storage_backend()

    @property
    def _storage_backends(self):
        return self.storage_config_handler.get_storage_backends()

    def _set_handlers(self, confman):
        self.storage_config_handler = confman.get_storage_config_handler()
        self.hosts_config_handler = confman.get_hosts_config_handler()
        self.openstack_config_handler = confman.get_openstack_config_handler()

    def handle(self, confman):
        """TODO: Set these dynamically according to user configuration instead."""
        try:
            self._set_handlers(confman)
            if ('ceph' in self._storage_backends):
                if self.storage_config_handler.is_ceph_enabled():
                    self.storage_config_handler.set_mons(self._managements)
                    self.storage_config_handler.set_ceph_mons(self._managements)
                    self.storage_config_handler.set_osds(self._storages)


        except configerror.ConfigError as exp:
            raise cmerror.CMError(str(exp))
