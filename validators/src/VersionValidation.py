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
import json

from cmframework.apis import cmvalidator
from cmdatahandlers.api import validation


class VersionValidation(cmvalidator.CMValidator):
    domain = 'cloud.version'
    version = [2, 0, 2]

    # Should be same as 'version' in release build
    devel_version = [2, 0, 2]

    # Example:
    # {1: 'This is the first change requiring new template version (1.1.0)',
    #  2: 'This is the second change requiring new template version (1.2.0)',
    #  3: 'This is the third change requiring new template version (1.3.0)'}
    change_log = {}

    def get_subscription_info(self):
        logging.debug('get_subscription info called')
        return r'^cloud\.version$'

    def validate_set(self, dict_key_value):
        logging.debug('validate_set called with %s' % str(dict_key_value))

        for key, value in dict_key_value.iteritems():
            version = json.loads(value)
            if key == self.domain:
                self.validate_version(version)
            else:
                raise validation.ValidationError('Unexpected configuration %s' % key)

    def validate_delete(self, prop):
        logging.debug('validate_delete called with %s' % str(prop))
        raise validation.ValidationError('%s cannot be deleted' % self.domain)

    def validate_version(self, version_str):
        if not version_str:
            raise validation.ValidationError('Missing configuration template version')
        if not isinstance(version_str, basestring):
            raise validation.ValidationError('Version configuration should be a string')
        data = version_str.split('.')
        if len(data) != 3:
            raise validation.ValidationError('Invalid version data syntax in configuration')
        version = []
        for i in data:
            if not i.isdigit():
                raise validation.ValidationError('Version data does not consist of numbers')
            version.append(int(i))
        if self.version != self.devel_version and version == self.devel_version:
            msg = 'Accepting development version %s' % version_str
            logging.warning(msg)
        elif version[0] != self.version[0]:
            reason = 'Major configuration template version mismatch (%s does not match with %s)' \
                     % (version_str, str(self.version))
            raise validation.ValidationError(reason)
        elif version[1] != self.version[1]:
            reason = 'Configuration template version mismatch (%s does not match with %s)' \
                     % (version_str, str(self.version))
            self.log_changes(version[1])
            raise validation.ValidationError(reason)
        elif version[2] != self.version[2]:
            msg = 'Minor configuration template version mismatch, check the latest template changes'
            logging.warning(msg)

    def log_changes(self, version):
        for key, log in self.change_log.iteritems():
            if key > version:
                logging.warning('Changes in template version %s.%s.0: %s' % (str(self.version[0]),
                                                                             str(key), log))
