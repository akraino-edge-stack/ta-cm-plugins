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
from netaddr import IPRange
from netaddr import IPNetwork

from cmframework.apis import cmvalidator
from cmdatahandlers.api import validation
from cmdatahandlers.api import utils
from serviceprofiles import profiles as service_profiles


class ConfigurationDoesNotExist(Exception):
    pass


class HostsValidation(cmvalidator.CMValidator):
    domain = 'cloud.hosts'
    management_profile = 'management'
    controller_profile = 'controller'
    caas_master_profile = 'caas_master'
    caas_worker_profile = 'caas_worker'
    base_profile = 'base'
    storage_profile = 'storage'

    storage_profile_attr = 'cloud.storage_profiles'
    network_profile_attr = 'cloud.network_profiles'
    performance_profile_attr = 'cloud.performance_profiles'
    networking_attr = 'cloud.networking'
    MIN_PASSWORD_LENGTH = 8

    def get_subscription_info(self):
        logging.debug('get_subscription info called')
        hosts = r'cloud\.hosts'
        net_profiles = r'cloud\.network_profiles'
        storage_profiles = r'cloud\.storage_profiles'
        perf_profiles = r'cloud\.performance_profiles'
        net = r'cloud\.networking'
        return '^%s|%s|%s|%s|%s$' % (hosts, net_profiles, storage_profiles, perf_profiles, net)

    def validate_set(self, dict_key_value):
        logging.debug('HostsValidation: validate_set called with %s', dict_key_value)

        for key, value in dict_key_value.iteritems():
            value_dict = {} if not value else json.loads(value)
            if not value_dict:
                if key != self.storage_profile_attr:
                    raise validation.ValidationError('No value for %s' % key)

            if key == self.domain:
                if not isinstance(value_dict, dict):
                    raise validation.ValidationError('%s value is not a dict' % self.domain)

                net_profile_dict = self.get_domain_dict(dict_key_value,
                                                        self.network_profile_attr)
                storage_profile_dict = self.get_domain_dict(dict_key_value,
                                                            self.storage_profile_attr)
                perf_profile_dict = self.get_domain_dict(dict_key_value,
                                                         self.performance_profile_attr)
                networking_dict = self.get_domain_dict(dict_key_value,
                                                       self.networking_attr)
                self.validate_hosts(value_dict,
                                    net_profile_dict,
                                    storage_profile_dict,
                                    perf_profile_dict,
                                    networking_dict)

                self.validate_scale_in(dict_key_value)

            elif key == self.network_profile_attr:
                profile_list = [] if not value_dict else value_dict.keys()

                host_dict = self.get_domain_dict(dict_key_value, self.domain)
                perf_profile_config = self.get_domain_dict(dict_key_value,
                                                           self.performance_profile_attr)
                storage_profile_config = self.get_domain_dict(dict_key_value,
                                                              self.storage_profile_attr)
                net_profile_dict = self.get_domain_dict(dict_key_value,
                                                        self.network_profile_attr)
                networking_dict = self.get_domain_dict(dict_key_value,
                                                       self.networking_attr)

                self.validate_network_ranges(host_dict, net_profile_dict, networking_dict)

                for host_name, host_data in host_dict.iteritems():
                    attr = 'network_profiles'
                    profiles = host_data.get(attr)
                    profile_name = profiles[0]
                    self.validate_profile_list(profiles, profile_list, host_name, attr)

                    performance_profiles = host_data.get('performance_profiles')

                    if self.is_provider_type_ovs_dpdk(profile_name, value_dict):
                        if self.base_profile not in host_data['service_profiles']:
                            reason = 'Missing base service profile with ovs_dpdk'
                            reason += ' type provider network'
                            raise validation.ValidationError(reason)
                        if not performance_profiles:
                            reason = \
                                'Missing performance profiles with ovs_dpdk type provider network'
                            raise validation.ValidationError(reason)
                        self.validate_performance_profile(perf_profile_config,
                                                          performance_profiles[0])

                    if self.is_provider_type_sriov(profile_name, value_dict):
                        if not self.is_sriov_allowed_for_host(host_data['service_profiles']):
                            reason = 'Missing base or caas_* service profile'
                            reason += ' with SR-IOV type provider network'
                            raise validation.ValidationError(reason)

                    subnet_name = 'infra_internal'
                    if not self.network_is_mapped(value_dict.get(profile_name), subnet_name):
                        raise validation.ValidationError('%s is not mapped for %s' % (subnet_name,
                                                                                      host_name))
                    if self.management_profile in host_data['service_profiles']:
                        subnet_name = 'infra_external'
                        if not self.network_is_mapped(value_dict.get(profile_name), subnet_name):
                            raise validation.ValidationError('%s is not mapped for %s' %
                                                             (subnet_name, host_name))
                    else:
                        subnet_name = 'infra_external'
                        if self.network_is_mapped(value_dict.get(profile_name), subnet_name):
                            raise validation.ValidationError('%s is mapped for %s' %
                                                             (subnet_name, host_name))

                    if self.storage_profile in host_data['service_profiles']:
                        storage_profile_list = host_data.get('storage_profiles')
                        subnet_name = 'infra_storage_cluster'
                        if not self.network_is_mapped(value_dict.get(profile_name), subnet_name) \
                                and self.is_ceph_profile(storage_profile_config,
                                                         storage_profile_list):
                            raise validation.ValidationError('%s is not mapped for %s' %
                                                             (subnet_name, host_name))

            elif key == self.storage_profile_attr:
                profile_list = [] if not value_dict else value_dict.keys()

                host_dict = self.get_domain_dict(dict_key_value, self.domain)

                for host_name, host_data in host_dict.iteritems():
                    attr = 'storage_profiles'
                    profiles = host_data.get(attr)
                    if profiles:
                        self.validate_profile_list(profiles, profile_list, host_name, attr)

            elif key == self.performance_profile_attr:
                profile_list = [] if not value_dict else value_dict.keys()

                host_dict = self.get_domain_dict(dict_key_value, self.domain)
                network_profile_config = self.get_domain_dict(dict_key_value,
                                                              self.network_profile_attr)

                for host_name, host_data in host_dict.iteritems():
                    attr = 'performance_profiles'
                    profiles = host_data.get(attr)
                    if profiles:
                        self.validate_profile_list(profiles, profile_list, host_name, attr)
                        self.validate_nonempty_performance_profile(value_dict, profiles[0],
                                                                   host_name)

                    network_profiles = host_data.get('network_profiles')
                    if self.is_provider_type_ovs_dpdk(network_profiles[0], network_profile_config):
                        if not profiles:
                            reason = \
                                'Missing performance profiles with ovs_dpdk type provider network'
                            raise validation.ValidationError(reason)
                        self.validate_performance_profile(value_dict,
                                                          profiles[0])
            elif key == self.networking_attr:
                networking_dict = value_dict

                hosts_dict = self.get_domain_dict(dict_key_value, self.domain)
                profile_config = self.get_domain_dict(dict_key_value,
                                                      self.network_profile_attr)

                self.validate_network_ranges(hosts_dict, profile_config, networking_dict)

            else:
                raise validation.ValidationError('Unexpected configuration %s' % key)

    def validate_delete(self, props):
        logging.debug('validate_delete called with %s', props)
        if self.domain in props:
            raise validation.ValidationError('%s cannot be deleted' % self.domain)
        else:
            raise validation.ValidationError('References in %s, cannot be deleted' % self.domain)

    def validate_hosts(self, hosts_config, nw_profile_config,
                       storage_profile_config, perf_profile_config,
                       networking_config):
        net_profile_list = [] if not nw_profile_config \
                              else nw_profile_config.keys()
        storage_profile_list = [] if not storage_profile_config else storage_profile_config.keys()
        performance_profile_list = [] if not perf_profile_config else perf_profile_config.keys()

        service_profile_list = service_profiles.Profiles().get_service_profiles()

        bases = []
        storages = []
        caas_masters = []
        managements = []

        for key, value in hosts_config.iteritems():
            # Hostname
            if not re.match(r'^[\da-z][\da-z-]*$', key) or len(key) > 63:
                raise validation.ValidationError('Invalid hostname %s' % key)

            # Network domain
            attr = 'network_domain'
            network_domain = value.get(attr)
            if not network_domain:
                reason = 'Missing %s for %s' % (attr, key)
                raise validation.ValidationError(reason)

            # Network profiles
            attr = 'network_profiles'
            profiles = value.get(attr)
            self.validate_profile_list(profiles, net_profile_list, key, attr)
            if len(profiles) != 1:
                reason = 'More than one %s defined for %s' % (attr, key)
                raise validation.ValidationError(reason)

            nw_profile_name = profiles[0]
            subnet_name = 'infra_internal'
            if not self.network_is_mapped(nw_profile_config.get(nw_profile_name), subnet_name):
                raise validation.ValidationError('%s is not mapped for %s' % (subnet_name, key))

            # Performance profiles
            attr = 'performance_profiles'
            perf_profile = None
            profiles = value.get(attr)
            if profiles:
                self.validate_profile_list(profiles, performance_profile_list,
                                           key, attr)
                if len(profiles) != 1:
                    reason = 'More than one %s defined for %s' % (attr, key)
                    raise validation.ValidationError(reason)
                perf_profile = profiles[0]
                self.validate_nonempty_performance_profile(perf_profile_config, perf_profile, key)

            if self.is_provider_type_ovs_dpdk(nw_profile_name, nw_profile_config):
                if not profiles:
                    reason = 'Missing performance profiles with ovs_dpdk type provider network'
                    raise validation.ValidationError(reason)
                self.validate_performance_profile(perf_profile_config, perf_profile)

            # Service profiles
            attr = 'service_profiles'
            profiles = value.get(attr)
            self.validate_profile_list(profiles, service_profile_list, key, attr)
            if self.is_provider_type_ovs_dpdk(nw_profile_name, nw_profile_config):
                if self.base_profile not in profiles:
                    reason = 'Missing base service profile with ovs_dpdk type provider network'
                    raise validation.ValidationError(reason)
            if self.is_provider_type_sriov(nw_profile_name, nw_profile_config):
                if not self.is_sriov_allowed_for_host(profiles):
                    reason = 'Missing base or caas_* service profile'
                    reason += ' with SR-IOV type provider network'
                    raise validation.ValidationError(reason)
            if perf_profile:
                if not self.is_perf_allowed_for_host(profiles):
                    reason = 'Missing base or caas_* service profile'
                    reason += ' with performance profile host'
                    raise validation.ValidationError(reason)
            if self.management_profile in profiles:
                managements.append(key)
                subnet_name = 'infra_external'
                if not self.network_is_mapped(nw_profile_config.get(nw_profile_name), subnet_name):
                    raise validation.ValidationError('%s is not mapped for %s' % (subnet_name, key))
            else:
                subnet_name = 'infra_external'
                if self.network_is_mapped(nw_profile_config.get(nw_profile_name), subnet_name):
                    raise validation.ValidationError('%s is mapped for %s' % (subnet_name, key))

            if self.base_profile in profiles:
                bases.append(key)
            if self.caas_master_profile in profiles:
                caas_masters.append(key)

            if self.storage_profile in profiles:
                storages.append(key)
                st_profiles = value.get('storage_profiles')
                self.validate_profile_list(st_profiles, storage_profile_list,
                                           key, 'storage_profiles')
                subnet_name = 'infra_storage_cluster'
                if not self.network_is_mapped(nw_profile_config.get(nw_profile_name), subnet_name) \
                        and self.is_ceph_profile(storage_profile_config, st_profiles):
                    raise validation.ValidationError('%s is not mapped for %s' % (subnet_name, key))

            # HW management
            self.validate_hwmgmt(value.get('hwmgmt'), key)

            # MAC address
            self.validate_mac_list(value.get('mgmt_mac'))

            # Preallocated IP validation
            self.validate_preallocated_ips(value, nw_profile_config, networking_config)

        # Check duplicated Preallocated IPs
        self.search_for_duplicate_ips(hosts_config)

        # There should be least one management node
        if not managements and not caas_masters:
            reason = 'No management node defined'
            raise validation.ValidationError(reason)

        # Number of caas_masters 1 or 3
        if caas_masters:
            if len(caas_masters) != 1 and len(caas_masters) != 3:
                reason = 'Unexpected number of caas_master nodes %d' % len(caas_masters)
                raise validation.ValidationError(reason)

        # Number of management nodes 1 or 3
        if managements:
            if len(managements) != 1 and len(managements) != 3:
                reason = 'Unexpected number of controller nodes %d' % len(managements)
                raise validation.ValidationError(reason)

        # All managements must be in same network domain
        management_network_domain = None
        for management in managements:
            if management_network_domain is None:
                management_network_domain = hosts_config[management].get('network_domain')
            else:
                if not management_network_domain == hosts_config[management].get('network_domain'):
                    reason = 'All management nodes must belong to the same networking domain'
                    raise validation.ValidationError(reason)

        if len(managements) == 3 and len(storages) < 2:
            raise validation.ValidationError('There are not enough storage nodes')

        self.validate_network_ranges(hosts_config, nw_profile_config, networking_config)

    def validate_network_ranges(self, hosts_config, nw_profile_config, networking_config):
        host_counts = {}  # (infra_network, network_domain) as a key, mapped host count as a value
        for host_conf in hosts_config.itervalues():
            if (isinstance(host_conf, dict) and
                    host_conf.get('network_profiles') and
                    isinstance(host_conf['network_profiles'], list) and
                    host_conf['network_profiles']):
                domain = host_conf.get('network_domain')
                profile = nw_profile_config.get(host_conf['network_profiles'][0])
                if (isinstance(profile, dict) and
                        profile.get('interface_net_mapping') and
                        isinstance(profile['interface_net_mapping'], dict)):
                    for infras in profile['interface_net_mapping'].itervalues():
                        if isinstance(infras, list):
                            for infra in infras:
                                key = (infra, domain)
                                if key in host_counts:
                                    host_counts[key] += 1
                                else:
                                    host_counts[key] = 1
        for (infra, domain), count in host_counts.iteritems():
            self.validate_infra_network_range(infra, domain, networking_config, count)

    def validate_infra_network_range(self, infra, network_domain, networking_config, host_count):
        infra_conf = networking_config.get(infra)
        if not isinstance(infra_conf, dict):
            return

        domains_conf = infra_conf.get('network_domains')
        if not isinstance(domains_conf, dict) or network_domain not in domains_conf:
            reason = '%s does not contain %s network domain configuration' % \
                (infra, network_domain)
            raise validation.ValidationError(reason)
        cidr = domains_conf[network_domain].get('cidr')
        start = domains_conf[network_domain].get('ip_range_start')
        end = domains_conf[network_domain].get('ip_range_end')

        if not start and cidr:
            start = str(IPNetwork(cidr)[1])
        if not end and cidr:
            end = str(IPNetwork(cidr)[-2])
        required = host_count if infra != 'infra_external' else host_count + 1
        if len(IPRange(start, end)) < required:
            reason = 'IP range %s - %s does not contain %d addresses' % (start, end, required)
            raise validation.ValidationError(reason)

    def validate_profile_list(self, profile_list, profile_defs, host, attribute):
        if not profile_list:
            raise validation.ValidationError('Missing %s for %s' % (attribute, host))
        if not isinstance(profile_list, list):
            raise validation.ValidationError('%s %s value must be a list' % (host, attribute))
        for profile in profile_list:
            if profile not in profile_defs:
                raise validation.ValidationError('Unknown %s %s for %s' %
                                                 (attribute, profile, host))

    def validate_hwmgmt(self, hwmgmt, host):
        # this list may not be comprehensive, but it matches ironic's idea
        # of valid privileges.  In practice, we'll likely only see OPERATOR
        # and ADMINISTRATOR.  Case seems to matter here.
        valid_ipmi_priv = ['USER', 'CALLBACK', 'OPERATOR', 'ADMINISTRATOR']
        
        if not hwmgmt:
            raise validation.ValidationError('Missing hwmgmt configuration for %s' % host)
        if not hwmgmt.get('user'):
            raise validation.ValidationError('Missing hwmgmt username for %s' % host)
        if not hwmgmt.get('password'):
            raise validation.ValidationError('Missing hwmgmt password for %s' % host)
        # priv_level is optional, but should be in the valid range.
        priv_level = hwmgmt.get('priv_level')
        if priv_level not in valid_ipmi_priv:
            raise validation.ValidationError('Invalid IPMI privilege level %s for %s' %
                                             (priv_level, host))
        validationutils = validation.ValidationUtils()
        validationutils.validate_ip_address(hwmgmt.get('address'))

    def validate_nonempty_performance_profile(self, config, profile_name, host_name):
        profile = config.get(profile_name)
        if not isinstance(profile, dict) or not profile:
            reason = 'Empty performance profile %s defined for %s' % (profile_name, host_name)
            raise validation.ValidationError(reason)

    def validate_performance_profile(self, config, profile_name):
        attributes = ['default_hugepagesz', 'hugepagesz', 'hugepages',
                      'ovs_dpdk_cpus']
        profile = config.get(profile_name)
        if not profile:
            profile = {}
        for attr in attributes:
            if not profile.get(attr):
                raise validation.ValidationError('Missing %s value for performance profile %s'
                                                 % (attr, profile_name))

    def validate_mac_list(self, mac_list):
        if not mac_list:
            return

        if not isinstance(mac_list, list):
            raise validation.ValidationError('mgmt_mac value must be a list')

        for mac in mac_list:
            pattern = '[0-9a-f]{2}([-:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$'
            if not mac or not re.match(pattern, mac.lower()):
                raise validation.ValidationError('Invalid mac address syntax %s' % mac)

    def validate_preallocated_ips(self, host, nw_profile_config, networking_config):
        if not self.host_has_preallocated_ip(host):
            return
        validationutils = validation.ValidationUtils()
        for network_name, ip in host["pre_allocated_ips"].iteritems():
            for net_profile_name in host["network_profiles"]:
                if not self.is_network_in_net_profile(
                        network_name, nw_profile_config.get(net_profile_name)):
                    raise validation.ValidationError(
                        "Network %s is missing from network profile %s" %
                        (network_name, net_profile_name))
            network_domains = networking_config.get(network_name).get("network_domains")
            host_network_domain = host["network_domain"]
            subnet = network_domains.get(host_network_domain)["cidr"]
            validationutils.validate_ip_address(ip)
            utils.validate_ip_in_network(ip, subnet)

    def host_has_preallocated_ip(self, host):
        ips_field = "pre_allocated_ips"
        if ips_field in host and host.get(ips_field, {}) and all(host[ips_field]):
            return True
        return False

    def is_network_in_net_profile(self, network_name, network_profile):
        for networks in network_profile["interface_net_mapping"].itervalues():
            if network_name in networks:
                return True
        return False

    def search_for_duplicate_ips(self, hosts):
        ips_field = "pre_allocated_ips"
        hosts_with_preallocated_ip = {name: attributes
                                      for name, attributes in hosts.iteritems()
                                      if self.host_has_preallocated_ip(attributes)}
        for host_name, host in hosts_with_preallocated_ip.iteritems():
            other_hosts = {name: attributes
                           for name, attributes in hosts_with_preallocated_ip.iteritems()
                           if name != host_name}
            for other_host_name, other_host in other_hosts.iteritems():
                if self.host_has_preallocated_ip(other_host):
                    logging.debug(
                        "Checking %s and %s for duplicated preallocated IPs",
                        host_name, other_host_name)
                    duplicated_ip = self.is_ip_duplicated(host[ips_field], other_host[ips_field])
                    if duplicated_ip:
                        raise validation.ValidationError(
                            "%s and %s has duplicated IP address: %s" %
                            (host_name, other_host_name, duplicated_ip))

    def is_ip_duplicated(self, ips, other_host_ips):
        logging.debug("Checking for IP duplication from %s to %s", ips, other_host_ips)
        for network_name, ip in ips.iteritems():
            if (network_name in other_host_ips and
                    ip == other_host_ips[network_name]):
                return ip
        return False

    def get_attribute_value(self, config, name_list):
        value = config
        for name in name_list:
            value = None if not isinstance(value, dict) else value.get(name)
            if not value:
                break
        return value

    def get_domain_dict(self, config, domain_name):
        client = self.get_plugin_client()
        str_value = config.get(domain_name)
        if not str_value:
            str_value = client.get_property(domain_name)
        dict_value = {} if not str_value else json.loads(str_value)
        return dict_value

    def is_provider_type_ovs_dpdk(self, profile_name, profile_config):
        path = [profile_name, 'provider_network_interfaces']
        provider_ifs = self.get_attribute_value(profile_config, path)
        if provider_ifs:
            for value in provider_ifs.values():
                if value.get('type') == 'ovs-dpdk':
                    return True
        return False

    def is_provider_type_sriov(self, profile_name, profile_config):
        path = [profile_name, 'sriov_provider_networks']
        if self.get_attribute_value(profile_config, path):
            return True
        return False

    def is_sriov_allowed_for_host(self, profiles):
        return (self.base_profile in profiles or
                self.caas_worker_profile in profiles or
                self.caas_master_profile in profiles)

    def is_perf_allowed_for_host(self, profiles):
        return self.is_sriov_allowed_for_host(profiles)

    def network_is_mapped(self, network_profile, name):
        mapping = network_profile.get('interface_net_mapping')
        if isinstance(mapping, dict):
            for interface in mapping.values():
                if name in interface:
                    return True
        return False

    def is_ceph_profile(self, storage_profiles, profile_list):
        ceph = 'ceph'
        for profile in profile_list:
            backend = storage_profiles[profile].get('backend')
            if backend == ceph:
                return True
        return False

    def _get_type_of_nodes(self, nodetype, config):
        nodes = [k for k, v in config.iteritems() if nodetype in v['service_profiles']]
        return nodes

    def _get_storage_nodes(self, config):
        return self._get_type_of_nodes(self.storage_profile, config)

    def _get_changed_hosts_config(self, config, domain_name):
        str_value = config.get(domain_name)
        return {} if not str_value else json.loads(str_value)

    def _get_running_hosts_config(self):
        return self.get_domain_dict({}, self.domain)

    def _get_number_of_changed_storage_hosts(self, changes):
        conf = self._get_changed_hosts_config(changes, self.domain)
        num = len(self._get_storage_nodes(conf))
        logging.debug(
            'HostsValidator: number of changed storage hosts: %s', str(num))
        return num

    def _get_number_of_old_storage_hosts(self):
        conf = self._get_running_hosts_config()
        if conf:
            num = len(self._get_storage_nodes(conf))
            logging.debug(
                'HostsValidator: number of existing storage hosts: %s', str(num))
            return num
        raise ConfigurationDoesNotExist(
            "The running hosts configuration does not exist -> deployment ongoing.")

    def _validate_only_one_storage_host_removed(self, changes):
        num_existing_storage_hosts = self._get_number_of_old_storage_hosts()
        if self._get_number_of_changed_storage_hosts(changes) < num_existing_storage_hosts-1:
            raise validation.ValidationError(
                "It is allowed to scale-in only 1 storage node at a time.")

    def validate_scale_in(self, changes):
        try:
            self._validate_only_one_storage_host_removed(changes)
        except ConfigurationDoesNotExist as exc:
            logging.debug(str(exc))
            return
