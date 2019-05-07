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


class UsersValidation(cmvalidator.CMValidator):
    domain = 'cloud.users'

    def get_subscription_info(self):
        logging.debug('get_subscription info called')
        return r'^cloud\.users$'

    def validate_set(self, dict_key_value):
        user_attr = 'admin_user_name'
        passwd_attr = 'admin_user_password'
        init_user_attr = 'initial_user_name'
        init_passwd_attr = 'initial_user_password'

        logging.debug('validate_set called with %s' % str(dict_key_value))

        value_str = dict_key_value.get(self.domain)
        value_dict = {} if not value_str else json.loads(value_str)
        if not value_dict:
            raise validation.ValidationError('No value for %s' % self.domain)
        if not isinstance(value_dict, dict):
            raise validation.ValidationError('%s value is not a dict' % self.domain)

        utils = validation.ValidationUtils()
        user = value_dict.get(user_attr)
        if user:
            utils.validate_username(user)
        else:
            raise validation.ValidationError('Missing %s' % user_attr)
        um_user = value_dict.get(init_user_attr)
        if um_user:
            utils.validate_username(um_user)
        else:
            raise validation.ValidationError('Missing %s' % init_user_attr)

        if not value_dict.get(passwd_attr):
            raise validation.ValidationError('Missing %s' % passwd_attr)
        if not value_dict.get(init_passwd_attr):
            raise validation.ValidationError('Missing %s' % init_passwd_attr)

    def validate_delete(self, dict_key_value):
        logging.debug('validate_delete called with %s' % str(dict_key_value))
        raise validation.ValidationError('%s cannot be deleted' % self.domain)
