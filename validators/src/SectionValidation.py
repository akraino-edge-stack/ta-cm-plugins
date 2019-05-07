#!/usr/bin/python
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

import logging

from cmframework.apis import cmvalidator
from cmdatahandlers.api import validation


class SectionValidation(cmvalidator.CMValidator):

    Required = ['cloud.name', 'cloud.version', 'cloud.time', 'cloud.users', 'cloud.networking',
                'cloud.storage', 'cloud.hosts', 'cloud.network_profiles',
                'cloud.storage_profiles', 'cloud.host_os']

    filterstr = r'^cloud\.'

    def get_subscription_info(self):
        logging.debug('get_subscription info called')
        return self.filterstr

    def validate_set(self, dict_key_value):
        logging.debug('validate_set called with %s', str(dict_key_value))

        key_list = dict_key_value.keys()
        self.validate_sections(key_list)

    def validate_delete(self, prop):
        # Domain specific validators should take care of validating deletion
        pass

    def validate_sections(self, sections):
        names = []
        missing = ''
        client = self.get_plugin_client()

        for name in self.Required:
            if name not in sections:
                names.append(name)
        properties = client.get_properties(self.filterstr)
        keys = properties.keys()
        for name in names:
            if name not in keys:
                missing += ', ' + name if missing else name
        if missing:
            raise validation.ValidationError('Mandatory sections missing from configuration: %s'
                                             % missing)
