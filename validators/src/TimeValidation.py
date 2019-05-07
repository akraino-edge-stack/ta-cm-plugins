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

# pylint: disable=line-too-long

import logging
import json
import pytz
import yaml
import requests
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

from cmframework.apis import cmvalidator
from cmdatahandlers.api import validation


class TimeValidation(cmvalidator.CMValidator):
    domain = 'cloud.time'
    supported_authentication_types = ['none', 'crypto', 'symmetric']

    def get_subscription_info(self):
        logging.debug('get_subscription info called')
        return r'^cloud\.time$'

    def validate_set(self, dict_key_value):
        ntp_attr = 'ntp_servers'
        logging.debug('validate_set called with %s' % str(dict_key_value))

        for key, value in dict_key_value.iteritems():
            value_dict = json.loads(value)
            if not value_dict:
                raise validation.ValidationError('No value for %s' % key)
            if not isinstance(value_dict, dict):
                raise validation.ValidationError('%s value is not a dict' % self.domain)

            if key == self.domain:
                ntp_list = value_dict.get(ntp_attr)

                self.validate_ntp(ntp_list)

                attr = 'zone'
                zone = value_dict.get(attr)
                if zone:
                    self.validate_timezone(zone)
                else:
                    raise validation.ValidationError('Missing timezone %s' % attr)

                auth_type = value_dict.get('auth_type')
                if auth_type:
                    self.validate_authtype(auth_type)
                else:
                    raise validation.ValidationError('Missing authentication type for NTP')

                filepath = value_dict.get('serverkeys_path')
                if auth_type != 'none' and filepath == '':
                    raise validation.ValidationError('The serverkeys_path is missing')
                elif auth_type == 'none':
                    pass
                else:
                    self.validate_filepath(filepath)
                    self.validate_yaml_format(filepath, auth_type)
            else:
                raise validation.ValidationError('Unexpected configuration %s' % key)

    def validate_delete(self, dict_key_value):
        logging.debug('validate_delete called with %s' % str(dict_key_value))
        raise validation.ValidationError('%s cannot be deleted' % self.domain)

    def validate_ntp(self, ntp_list):
        if not ntp_list:
            raise validation.ValidationError('Missing NTP configuration')

        if not isinstance(ntp_list, list):
            raise validation.ValidationError('NTP servers value must be a list')
        utils = validation.ValidationUtils()
        for ntp in ntp_list:
            utils.validate_ip_address(ntp)

    def validate_timezone(self, value):
        try:
            pytz.timezone(value)
        except pytz.UnknownTimeZoneError as exc:
            raise validation.ValidationError("Invalid time zone: {0}".format(exc))

    def validate_authtype(self, auth_type):
        if auth_type not in TimeValidation.supported_authentication_types:
            raise validation.ValidationError(
                'The provided authentication method for NTP is not supported')

    def validate_filepath(self, filepath):
        try:
            val = URLValidator()
            val(filepath)
        except ValidationError:
            raise validation.ValidationError('The url: "%s" is not a valid url!' % filepath)

    def validate_yaml_format(self, url, auth_type):
        if url.startswith("file://"):
            path = url.lstrip("file://")
            try:
                with open(path) as f:
                    f_content = f.read()
            except IOError:
                raise validation.ValidationError('The file: "%s" is not present on the system!'
                                                 % url)
        else:
            try:
                r = requests.get(url)
                if r['status_code'] != 200:
                    raise requests.exceptions.ConnectionError()
                f_content = r['content']
            except requests.exceptions.ConnectionError:
                raise validation.ValidationError('The url: "%s" is not reachable!' % url)
        try:
            yaml_content = yaml.load(f_content)
        except yaml.YAMLError:
            raise validation.ValidationError('The validation of the yamlfile failed!')
        for item in yaml_content:
            srv = item.keys()[0]
            if auth_type == 'symmetric' and not isinstance(item[srv], str):
                raise validation.ValidationError('The yamlfile contains invalid data! '
                                                 '(The authentication method looks like it\'s symmetric.)')
            elif auth_type == 'crypto' and isinstance(item[srv], dict):
                if (item[srv]['type'] != 'iff' or item[srv]['type'] != 'gq' or
                    item[srv]['type'] != 'mv')\
                   and (not isinstance(item[srv]['keys'], list)):
                    raise validation.ValidationError('The yamlfile contains invalid data! '
                                                     '(The authentication method looks like it\'s crypto.)')
            else:
                raise validation.ValidationError('The yamlfile contains invalid data!')
