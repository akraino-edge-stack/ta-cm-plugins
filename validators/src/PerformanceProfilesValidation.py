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

import json

from cmdatahandlers.api import validation
from cmframework.apis import cmvalidator


class PerformanceProfilesValidation(cmvalidator.CMValidator):
    DOMAIN = 'cloud.performance_profiles'
    SUBSCRIPTION = r'^cloud\.performance_profiles$'

    HUGEPAGESZ = 'hugepagesz'
    DEFAULT_HUGEPAGESZ = 'default_hugepagesz'
    HUGEPAGES = 'hugepages'
    PLATFORM_CPUS = 'platform_cpus'
    DPDK_CPUS = 'ovs_dpdk_cpus'
    CAAS_CPU_POOLS = 'caas_cpu_pools'
    CAAS_CPU_POOL_ATTRIBUTES = ['exclusive_pool_percentage', 'shared_pool_percentage']
    CAAS_CPU_POOL_SHARE = 'caas_cpu_pool_share'
    TUNING = 'tuning'

    NUMA0 = 'numa0'
    NUMA1 = 'numa1'
    NUMA_VALUES = [NUMA0, NUMA1]

    HUGEPAGESZ_VALUES = ['2M', '1G']
    TUNING_OPTIONS = ['low_latency', 'standard']

    INFO_HUGEPAGESZ = 'Valid values: %s' % HUGEPAGESZ_VALUES
    INFO_HUGEPAGES = 'Must be positive integer'
    INFO_CPUS = 'Must be zero or positive integer'
    INFO_PLATFORM_CPUS = 'Platform requires at least one core from NUMA0'
    INFO_TUNING = 'Valid tuning options are %s' % TUNING_OPTIONS

    ERR_MISSING_DATA = 'Performance profiles validation input does not contain {} data'
    ERR_INVALID_VALUE = 'Invalid %s value in performance profile {}: %s'
    ERR_INVALID_CONFIG = 'Invalid {} config (not a dict)'

    ERR_HUGEPAGESZ = ERR_INVALID_VALUE % (HUGEPAGESZ, INFO_HUGEPAGESZ)
    ERR_DEFAULT_HUGEPAGESZ = ERR_INVALID_VALUE % (DEFAULT_HUGEPAGESZ, INFO_HUGEPAGESZ)
    ERR_HUGEPAGES = ERR_INVALID_VALUE % (HUGEPAGES, INFO_HUGEPAGES)

    ERR_NUMA = "Invalid NUMA value in performance profile {}"
    ERR_CPUS = ERR_INVALID_VALUE % ("platform/ovs_dpdk cpu", INFO_CPUS)
    ERR_PLATFORM_CPUS = ERR_INVALID_VALUE % ("platform_cpus", INFO_PLATFORM_CPUS)
    ERR_CPU_POOL_RATIO = 'caas_cpu_pools total cpu percentage exceeded'
    ERR_CAAS_CPU_POOL_TYPE = 'caas_cpu_pools percentage values should be integer'
    ERR_CAAS_DEFAULT_POOL = 'caas_cpu_pool_share value should be integer between 0 and 100'
    ERR_TUNING = "Invalid %s value in {}. %s" % (TUNING, INFO_TUNING)

    @staticmethod
    def raise_error(context, err_type):
        raise validation.ValidationError(err_type.format(context))

    def get_subscription_info(self):
        return self.SUBSCRIPTION

    def validate_set(self, props):
        conf = self.get_conf(props)
        if isinstance(conf, dict):
            self.validate(conf)
        elif conf:
            self.raise_error(self.DOMAIN, self.ERR_INVALID_CONFIG)

    def get_conf(self, props):
        if not isinstance(props, dict) or self.DOMAIN not in props:
            self.raise_error(self.DOMAIN, self.ERR_MISSING_DATA)
        return json.loads(props[self.DOMAIN])

    def validate(self, conf):
        for profile, entries in conf.iteritems():
            if isinstance(entries, dict):
                self.validate_profile(profile, entries)

    def validate_profile(self, profile, entries):
        for key, value in entries.iteritems():
            self.validate_value(profile, key, value)

    def validate_value(self, profile, key, value):
        if key == self.HUGEPAGESZ:
            self.validate_hugepagesz(profile, value)
        elif key == self.DEFAULT_HUGEPAGESZ:
            self.validate_default_hugepagesz(profile, value)
        elif key == self.HUGEPAGES:
            self.validate_hugepages(profile, value)
        elif key == self.PLATFORM_CPUS:
            self.validate_platform_cpus(profile, value)
        elif key == self.DPDK_CPUS:
            self.validate_ovs_dpdk_cpus(profile, value)
        elif key == self.CAAS_CPU_POOLS:
            self.validate_caas_cpu_pools(profile, value)
        elif key == self.CAAS_CPU_POOL_SHARE:
            self.validate_caas_cpu_pool_share(value)
        elif key == self.TUNING:
            self.validate_tuning(profile, value)

    def validate_hugepagesz(self, profile, value):
        if value not in self.HUGEPAGESZ_VALUES:
            self.raise_error(profile, self.ERR_HUGEPAGESZ)

    def validate_default_hugepagesz(self, profile, value):
        if value not in self.HUGEPAGESZ_VALUES:
            self.raise_error(profile, self.ERR_DEFAULT_HUGEPAGESZ)

    def validate_hugepages(self, profile, value):
        if not (isinstance(value, (int, long)) and value > 0):
            self.raise_error(profile, self.ERR_HUGEPAGES)

    def validate_numa_names(self, profile, cpus):
        if isinstance(cpus, dict):
            for key in cpus.keys():
                if key not in self.NUMA_VALUES:
                    self.raise_error(profile, self.ERR_NUMA)

    def validate_cpu_values(self, profile, cpus):
        if isinstance(cpus, dict):
            for value in cpus.values():
                if not (isinstance(value, (int, long)) and value >= 0):
                    self.raise_error(profile, self.ERR_CPUS)

    def validate_platform_cpus(self, profile, cpus):
        self.validate_numa_names(profile, cpus)
        if cpus.get(self.NUMA1, None) is not None and cpus.get(self.NUMA0, None) is None:
            self.raise_error(profile, self.ERR_PLATFORM_CPUS)
        if cpus.get(self.NUMA1, None) is not None and cpus.get(self.NUMA0, None) == 0:
            self.raise_error(profile, self.ERR_PLATFORM_CPUS)
        self.validate_cpu_values(profile, cpus)

    def validate_ovs_dpdk_cpus(self, profile, cpus):
        self.validate_numa_names(profile, cpus)
        self.validate_cpu_values(profile, cpus)

    def validate_caas_cpu_pools(self, profile, pools):
        sum_ratio = 0
        self.allowed_attributes(profile, pools, self.CAAS_CPU_POOL_ATTRIBUTES)
        self.is_attribute_present(profile, pools, self.CAAS_CPU_POOL_ATTRIBUTES)
        for value in pools.values():
            if not isinstance(value, int) or (value > 100) or (value < 0):
                self.raise_error(profile, self.ERR_CAAS_CPU_POOL_TYPE)
            sum_ratio += value
        if sum_ratio > 100:
            self.raise_error(profile, self.ERR_CPU_POOL_RATIO)

    def validate_tuning(self, profile, option):
        if option not in self.TUNING_OPTIONS:
            self.raise_error(profile, self.ERR_TUNING)

    def allowed_attributes(self, profile, entries, allowed_attributes):
        for key in entries.keys():
            if key not in allowed_attributes:
                self.raise_error(profile, 'Attribute %s is not allowed in profile %s, '
                                 'allowed attributes: \"%s\"' %
                                 (key, profile, str(",".join(allowed_attributes))))

    def is_attribute_present(self, profile, entries, attributes):
        is_present = False
        for key in entries.keys():
            if key in attributes:
                is_present = True
        if not is_present:
            self.raise_error(profile, 'Profile: %s should contain at least one of the following '
                             'attributes: \"%s\"' % (profile, str(",".join(attributes))))

    def validate_caas_cpu_pool_share(self, value):
        if not isinstance(value, (int)) or (value > 100) or (value < 0):
            self.raise_error(value, self.ERR_CAAS_DEFAULT_POOL)
