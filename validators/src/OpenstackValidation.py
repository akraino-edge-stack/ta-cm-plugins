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

# pylint: disable=invalid-name, missing-docstring, too-few-public-methods,
# pylint: disable=logging-not-lazy, too-many-locals

import logging
import json

from cmframework.apis import cmvalidator
from cmdatahandlers.api import validation


class OpenstackValidationError(validation.ValidationError):
    pass


class OpenstackValidation(cmvalidator.CMValidator):
    domain = "cloud.openstack"

    def get_subscription_info(self):  # pylint: disable=no-self-use
        logging.debug('get_subscription info called')
        return r'^cloud\.openstack$'

    def validate_set(self, dict_key_value):
        logging.debug('validate_set called with %s' % str(dict_key_value))

        client = self.get_plugin_client()

        for key, value in dict_key_value.iteritems():
            value_str = value
            value_dict = json.loads(value_str)

            if key == self.domain:
                openstack_config = value_dict
                if not isinstance(value_dict, dict):
                    raise validation.ValidationError('%s value is not a dict' % self.domain)
            else:
                raise validation.ValidationError('Unexpected configuration %s' % key)
            self.validate_openstack(openstack_config)

    def validate_delete(self, properties):
        logging.debug('validate_delete called with %s' % str(properties))
        if self.domain in properties:
            raise validation.ValidationError('%s cannot be deleted' % self.domain)
        else:
            raise validation.ValidationError('References in %s, cannot be deleted' % self.domain)

    def validate_openstack(self, openstack_config):
        if not openstack_config:
            raise validation.ValidationError('No value for %s' % self.domain)

        self.validate_admin_password(openstack_config)

    @staticmethod
    def validate_admin_password(openstack_config):
        password = 'admin_password'
        passwd = openstack_config.get(password)
        if not passwd:
            raise validation.ValidationError('Missing %s' % password)
