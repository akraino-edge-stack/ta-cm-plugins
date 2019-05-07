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
import re

from cmframework.apis import cmvalidator
from cmdatahandlers.api import validation


class HostOSValidation(cmvalidator.CMValidator):
    domain = 'cloud.host_os'
    GRUB2_PASSWORD_PATTERN = r"^grub\.pbkdf2\.sha512\.\d+\.[0-9A-F]+\.[0-9A-F]+$"

    def get_subscription_info(self):
        logging.debug('get_subscription info called')
        return r'^cloud\.host_os$'

    def validate_set(self, dict_key_value):
        grub2pass_attr = 'grub2_password'
        lockout_time_attr = 'lockout_time'
        failed_login_attempts_attr = 'failed_login_attempts'
        logging.debug('validate_set called with %s' % str(dict_key_value))

        value_str = dict_key_value.get(self.domain, None)
        logging.debug('{0} domain value: {1}'.format(self.domain, value_str))
        if value_str is not None:
            value_dict = json.loads(value_str)

            if not isinstance(value_dict, dict):
                raise validation.ValidationError('%s value is not a dict' % self.domain)

            passwd = value_dict.get(grub2pass_attr)
            if passwd:
                self.validate_passwd_hash(passwd)

            lockout_t = value_dict.get(lockout_time_attr)
            if lockout_t:
                self.validate_lockout_time(lockout_t)

            failed_login_a = value_dict.get(failed_login_attempts_attr)
            if failed_login_a:
                self.validate_failed_login_attempts(failed_login_a)
        else:
            raise validation.ValidationError('Missing domain: %s' % self.domain)

    def validate_delete(self, dict_key_value):
        logging.debug('validate_delete called with %s' % str(dict_key_value))
        raise validation.ValidationError('%s cannot be deleted' % self.domain)

    def validate_passwd_hash(self, passwd_hash):
        if not re.match(self.GRUB2_PASSWORD_PATTERN, passwd_hash):
            raise validation.ValidationError('The passwd hash: "%s" is not a valid hash!' % passwd_hash)

    def validate_lockout_time(self, _lockout_time):
        if not re.match(r"^[0-9]+$", str(_lockout_time)):
            raise validation.ValidationError('The lockout time: "%s" is not valid!' % _lockout_time)

    def validate_failed_login_attempts(self, _failed_login_attempts):
        if not re.match(r"^[0-9]+$", str(_failed_login_attempts)):
            raise validation.ValidationError('The failed login attempts: "%s" is not valid!' % _failed_login_attempts)
