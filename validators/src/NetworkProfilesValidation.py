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

import json
import re

from cmdatahandlers.api import validation
from cmframework.apis import cmvalidator
from cmdatahandlers.api import utils


class NetworkProfilesValidation(cmvalidator.CMValidator):
    SUBSCRIPTION = r'^cloud\.network_profiles|cloud\.networking$'
    DOMAIN = 'cloud.network_profiles'
    NETWORKING = 'cloud.networking'

    MAX_IFACE_NAME_LEN = 15
    IFACE_NAME_MATCH = r'^[a-z][\da-z]+$'
    BOND_NAME_MATCH = r'^bond[\d]+$'

    INTERFACE_NET_MAPPING = 'interface_net_mapping'
    PROVIDER_NETWORK_INTERFACES = 'provider_network_interfaces'
    PROVIDER_NETWORKS = 'provider_networks'
    SRIOV_PROVIDER_NETWORKS = 'sriov_provider_networks'
    INTERFACES = 'interfaces'
    TRUSTED = 'trusted'
    VF_COUNT = 'vf_count'
    TYPE = 'type'
    DPDK_MAX_RX_QUEUES = 'dpdk_max_rx_queues'
    BONDING_INTERFACES = 'bonding_interfaces'
    LINUX_BONDING_OPTIONS = 'linux_bonding_options'
    OVS_BONDING_OPTIONS = 'ovs_bonding_options'

    TYPE_CAAS = 'caas'
    TYPE_OPENSTACK = 'openstack'
    TYPE_OVS = 'ovs'
    TYPE_OVS_DPDK = 'ovs-dpdk'
    TYPE_OVS_OFFLOAD_SRIOV = "ovs-offload-sriov"
    TYPE_OVS_OFFLOAD_VIRTIO = "ovs-offload-virtio"
    VALID_PROVIDER_TYPES = [TYPE_CAAS,
                            TYPE_OVS,
                            TYPE_OVS_DPDK,
                            TYPE_OVS_OFFLOAD_SRIOV,
                            TYPE_OVS_OFFLOAD_VIRTIO]
    SINGLE_NIC_UNSUPPORTED_TYPES = [TYPE_CAAS, TYPE_OVS_DPDK]
    VALID_SRIOV_TYPES = [TYPE_CAAS, TYPE_OPENSTACK]

    MODE_LACP = 'mode=lacp'
    MODE_LACP_LAYER34 = 'mode=lacp-layer34'
    MODE_AB = 'mode=active-backup'
    VALID_BONDING_OPTIONS = [MODE_LACP, MODE_LACP_LAYER34, MODE_AB]

    VLAN_RANGES = 'vlan_ranges'
    VLAN = 'vlan'
    MTU = 'mtu'
    DEFAULT_MTU = 1500
    NETWORK_DOMAINS = 'network_domains'

    UNTAGGED = 'untagged'

    INPUT_ERR_CONTEXT = 'validate_set() input'
    ERR_INPUT_NOT_DICT = 'Invalid %s, not a dictionary' % INPUT_ERR_CONTEXT

    ERR_MISSING = 'Missing {1} configuration in {0}'
    ERR_NOT_DICT = 'Invalid {1} value in {0}: Empty or not a dictionary'
    ERR_NOT_LIST = 'Invalid {1} value in {0}: Empty, contains duplicates or not a list'
    ERR_NOT_STR = 'Invalid {1} value in {0}: Not a string'
    ERR_NOT_INT = 'Invalid {1} value in {0}: Not an integer'
    ERR_NOT_BOOL = 'Invalid {1} value in {0}: Not a boolean value'

    ERR_INVALID_IFACE_NAME = 'Invalid interface name in {}'
    ERR_IFACE_NAME_LEN = 'Too long interface name in {}, max %s chars' % MAX_IFACE_NAME_LEN
    ERR_IFACE_VLAN = 'Interface in {0} cannot be vlan interface: {1}'
    ERR_IFACE_BOND = 'Interface in {0} cannot be bond interface: {1}'
    ERR_IFACE_NOT_BOND = 'Invalid bonding interface name {1} in {0}'
    ERR_NET_MAPPING_CONFLICT = 'Network {1} mapped to multiple interfaces in {0}'
    ERR_UNTAGGED_INFRA_CONFLICT = 'Multiple untagged networks on interface {1} in {0}'
    ERR_UNTAGGED_MTU_SIZE = 'Untagged network {1} in {0} has too small MTU, ' + \
                            'VLAN tagged networks with bigger MTU exists on the same interface'

    ERR_INVALID_PROVIDER_TYPE = \
        'Invalid provider network type for interface {}, valid types: %s' % \
        VALID_PROVIDER_TYPES
    ERR_INVALID_SRIOV_TYPE = \
        'Invalid sr-iov network type for network {}, valid types: %s' % \
        VALID_SRIOV_TYPES

    ERR_DPDK_MAX_RX_QUEUES = 'Invalid %s value {}, must be positive integer' % DPDK_MAX_RX_QUEUES
    ERR_MISSPLACED_MTU = 'Missplaced MTU inside %s interface {}' % PROVIDER_NETWORK_INTERFACES
    ERR_OVS_TYPE_CONFLICT = 'Cannot have both %s and %s types of provider networks in {}' % \
        (TYPE_OVS, TYPE_OVS_DPDK)
    ERR_DPDK_SRIOV_CONFLICT = 'Cannot have both %s and sr-iov on same interface in {}' % \
        TYPE_OVS_DPDK
    ERR_OFFLOAD_SRIOV_CONFLICT = 'Cannot have both %s and sr-iov on same profile in {}' % \
        TYPE_OVS_OFFLOAD_SRIOV
    ERR_OFFLOAD_DPDK_CONFLICT = 'Cannot have both %s and %s types of provider networks in {}' % \
        (TYPE_OVS_OFFLOAD_SRIOV, TYPE_OVS_DPDK)

    ERR_INVALID_BONDING_OPTIONS = 'Invalid {1} in {0}, valid options: %s' % VALID_BONDING_OPTIONS
    ERR_MISSING_BOND = 'Missing bonding interface definition for {1} in {0}'
    ERR_LACP_SLAVE_COUNT = 'Invalid bonding slave interface count for {1} in {0} ' + \
        'at least two interfaces required with %s' % MODE_LACP
    ERR_AB_SLAVE_COUNT = 'Invalid bonding slave interface count for {1} in {0}, ' + \
        'exactly two interfaces required with %s' % MODE_AB
    ERR_SLAVE_CONFLICT = 'Same interface mapped to multiple bond interfaces in {}'
    ERR_SLAVE_IN_NET = 'Network physical interface {1} mapped also as part of bond in {0}'

    ERR_SRIOV_MTU_SIZE = 'SR-IOV network {0} MTU {1} cannot be greater than interface {2} MTU {3}'
    ERR_SRIOV_INFRA_VLAN_CONFLICT = \
        'SR-IOV network {} vlan range is conflicting with infra network vlan'
    ERR_SRIOV_PROVIDER_VLAN_CONFLICT = \
        'SR-IOV network {} vlan range is conflicting with other provider network vlan'
    ERR_SINGLE_NIC_VIOLATION = \
        'Provider and infra networks on the same interface in {}: ' + \
        'Supported only if all networks on the same interface'
    ERR_SINGLE_NIC_PROVIDER_TYPE = \
        'Provider and infra networks on the same interface in {0}: ' + \
        'Not supported for {1} type of provider networks'
    ERR_INFRA_PROVIDER_VLAN_CONFLICT = \
        'Provider network {} vlan range is conflicting with infra network vlan'
    ERR_INFRA_PROVIDER_UNTAGGED_CONFLICT = \
        'Sharing untagged infra and provider network {} not supported'
    ERR_SRIOV_LACP_CONFLICT = 'Bonding mode %s not supported with SR-IOV networks' % MODE_LACP
    ERR_SRIOV_IFACE_CONFLICT = 'Same interface mapped to multiple SR-IOV networks in {}'
    ERR_VF_COUNT = 'SR-IOV network {} %s must be positive integer' % VF_COUNT

    ERR_PROVIDER_VLAN_CONFLICT = 'Provider network vlan ranges conflicting on interface {}'

    @staticmethod
    def err_input_not_dict():
        err = NetworkProfilesValidation.ERR_INPUT_NOT_DICT
        raise validation.ValidationError(err)

    @staticmethod
    def err_missing(context, key):
        err = NetworkProfilesValidation.ERR_MISSING.format(context, key)
        raise validation.ValidationError(err)

    @staticmethod
    def err_not_dict(context, key):
        err = NetworkProfilesValidation.ERR_NOT_DICT.format(context, key)
        raise validation.ValidationError(err)

    @staticmethod
    def err_not_list(context, key):
        err = NetworkProfilesValidation.ERR_NOT_LIST.format(context, key)
        raise validation.ValidationError(err)

    @staticmethod
    def err_not_str(context, key):
        raise validation.ValidationError(NetworkProfilesValidation.ERR_NOT_STR.format(context, key))

    @staticmethod
    def err_not_int(context, key):
        raise validation.ValidationError(NetworkProfilesValidation.ERR_NOT_INT.format(context, key))

    @staticmethod
    def err_not_bool(context, key):
        err = NetworkProfilesValidation.ERR_NOT_BOOL.format(context, key)
        raise validation.ValidationError(err)

    @staticmethod
    def err_invalid_iface_name(context):
        err = NetworkProfilesValidation.ERR_INVALID_IFACE_NAME.format(context)
        raise validation.ValidationError(err)

    @staticmethod
    def err_iface_name_len(context):
        err = NetworkProfilesValidation.ERR_IFACE_NAME_LEN.format(context)
        raise validation.ValidationError(err)

    @staticmethod
    def err_iface_vlan(context, iface):
        err = NetworkProfilesValidation.ERR_IFACE_VLAN.format(context, iface)
        raise validation.ValidationError(err)

    @staticmethod
    def err_iface_bond(context, iface):
        err = NetworkProfilesValidation.ERR_IFACE_BOND.format(context, iface)
        raise validation.ValidationError(err)

    @staticmethod
    def err_provnet_type(iface):
        err = NetworkProfilesValidation.ERR_INVALID_PROVIDER_TYPE.format(iface)
        raise validation.ValidationError(err)

    @staticmethod
    def err_sriov_type(network):
        err = NetworkProfilesValidation.ERR_INVALID_SRIOV_TYPE.format(network)
        raise validation.ValidationError(err)

    @staticmethod
    def err_dpdk_max_rx_queues(value):
        err = NetworkProfilesValidation.ERR_DPDK_MAX_RX_QUEUES.format(value)
        raise validation.ValidationError(err)

    @staticmethod
    def err_missplaced_mtu(iface):
        err = NetworkProfilesValidation.ERR_MISSPLACED_MTU.format(iface)
        raise validation.ValidationError(err)

    @staticmethod
    def err_iface_not_bond(context, iface):
        err = NetworkProfilesValidation.ERR_IFACE_NOT_BOND.format(context, iface)
        raise validation.ValidationError(err)

    @staticmethod
    def err_bonding_options(profile, options_type):
        err = NetworkProfilesValidation.ERR_INVALID_BONDING_OPTIONS.format(profile, options_type)
        raise validation.ValidationError(err)

    @staticmethod
    def err_missing_bond_def(profile, iface):
        err = NetworkProfilesValidation.ERR_MISSING_BOND.format(profile, iface)
        raise validation.ValidationError(err)

    @staticmethod
    def err_lacp_slave_count(profile, iface):
        err = NetworkProfilesValidation.ERR_LACP_SLAVE_COUNT.format(profile, iface)
        raise validation.ValidationError(err)

    @staticmethod
    def err_ab_slave_count(profile, iface):
        err = NetworkProfilesValidation.ERR_AB_SLAVE_COUNT.format(profile, iface)
        raise validation.ValidationError(err)

    @staticmethod
    def err_slave_conflict(profile):
        err = NetworkProfilesValidation.ERR_SLAVE_CONFLICT.format(profile)
        raise validation.ValidationError(err)

    @staticmethod
    def err_slave_in_net(profile, iface):
        err = NetworkProfilesValidation.ERR_SLAVE_IN_NET.format(profile, iface)
        raise validation.ValidationError(err)

    @staticmethod
    def err_ovs_type_conflict(profile):
        err = NetworkProfilesValidation.ERR_OVS_TYPE_CONFLICT.format(profile)
        raise validation.ValidationError(err)

    @staticmethod
    def err_offload_dpdk_conflict(profile):
        err = NetworkProfilesValidation.ERR_OFFLOAD_DPDK_CONFLICT.format(profile)
        raise validation.ValidationError(err)

    @staticmethod
    def err_dpdk_sriov_conflict(profile):
        err = NetworkProfilesValidation.ERR_DPDK_SRIOV_CONFLICT.format(profile)
        raise validation.ValidationError(err)

    @staticmethod
    def err_offload_sriov_conflict(profile):
        err = NetworkProfilesValidation.ERR_OFFLOAD_SRIOV_CONFLICT.format(profile)
        raise validation.ValidationError(err)

    @staticmethod
    def err_net_mapping_conflict(profile, network):
        err = NetworkProfilesValidation.ERR_NET_MAPPING_CONFLICT.format(profile, network)
        raise validation.ValidationError(err)

    @staticmethod
    def err_untagged_infra_conflict(profile, iface):
        err = NetworkProfilesValidation.ERR_UNTAGGED_INFRA_CONFLICT.format(profile, iface)
        raise validation.ValidationError(err)

    @staticmethod
    def err_untagged_mtu_size(context, network):
        err = NetworkProfilesValidation.ERR_UNTAGGED_MTU_SIZE.format(context, network)
        raise validation.ValidationError(err)

    @staticmethod
    def err_sriov_mtu_size(sriov_net, sriov_mtu, phys_iface, iface_mtu):
        err = NetworkProfilesValidation.ERR_SRIOV_MTU_SIZE.format(sriov_net, sriov_mtu,
                                                                  phys_iface, iface_mtu)
        raise validation.ValidationError(err)

    @staticmethod
    def err_sriov_infra_vlan_conflict(network):
        err = NetworkProfilesValidation.ERR_SRIOV_INFRA_VLAN_CONFLICT.format(network)
        raise validation.ValidationError(err)

    @staticmethod
    def err_sriov_provider_vlan_conflict(network):
        err = NetworkProfilesValidation.ERR_SRIOV_PROVIDER_VLAN_CONFLICT.format(network)
        raise validation.ValidationError(err)

    @staticmethod
    def err_single_nic_violation(profile):
        err = NetworkProfilesValidation.ERR_SINGLE_NIC_VIOLATION.format(profile)
        raise validation.ValidationError(err)

    @staticmethod
    def err_single_nic_provider_type(profile, provider_type):
        err = NetworkProfilesValidation.ERR_SINGLE_NIC_PROVIDER_TYPE.format(profile, provider_type)
        raise validation.ValidationError(err)

    @staticmethod
    def err_infra_provider_vlan_conflict(network):
        err = NetworkProfilesValidation.ERR_INFRA_PROVIDER_VLAN_CONFLICT.format(network)
        raise validation.ValidationError(err)

    @staticmethod
    def err_infra_provider_untagged_conflict(network):
        err = NetworkProfilesValidation.ERR_INFRA_PROVIDER_UNTAGGED_CONFLICT.format(network)
        raise validation.ValidationError(err)

    @staticmethod
    def err_sriov_lacp_conflict():
        err = NetworkProfilesValidation.ERR_SRIOV_LACP_CONFLICT
        raise validation.ValidationError(err)

    @staticmethod
    def err_sriov_iface_conflict():
        err = NetworkProfilesValidation.ERR_SRIOV_IFACE_CONFLICT
        raise validation.ValidationError(err)

    @staticmethod
    def err_vf_count(network):
        err = NetworkProfilesValidation.ERR_VF_COUNT.format(network)
        raise validation.ValidationError(err)

    @staticmethod
    def err_provider_vlan_conflict(iface):
        err = NetworkProfilesValidation.ERR_PROVIDER_VLAN_CONFLICT.format(iface)
        raise validation.ValidationError(err)

    @staticmethod
    def is_dict(conf):
        return isinstance(conf, dict)

    @staticmethod
    def is_bond_iface(iface):
        return re.match(NetworkProfilesValidation.BOND_NAME_MATCH, iface)

    @staticmethod
    def is_non_empty_dict(conf):
        return isinstance(conf, dict) and len(conf) > 0

    @staticmethod
    def key_exists(conf_dict, key):
        return key in conf_dict

    @staticmethod
    def val_is_int(conf_dict, key):
        return isinstance(conf_dict[key], (int, long))

    @staticmethod
    def val_is_bool(conf_dict, key):
        return isinstance(conf_dict[key], bool)

    @staticmethod
    def val_is_str(conf_dict, key):
        return isinstance(conf_dict[key], basestring)

    @staticmethod
    def val_is_non_empty_list(conf_dict, key):
        return (isinstance(conf_dict[key], list) and
                len(conf_dict[key]) > 0 and
                len(conf_dict[key]) == len(set(conf_dict[key])))

    @staticmethod
    def val_is_non_empty_dict(conf_dict, key):
        return NetworkProfilesValidation.is_non_empty_dict(conf_dict[key])

    @staticmethod
    def key_must_exist(conf_dict, entry, key):
        if not NetworkProfilesValidation.key_exists(conf_dict[entry], key):
            NetworkProfilesValidation.err_missing(entry, key)

    @staticmethod
    def must_be_str(conf_dict, entry, key):
        NetworkProfilesValidation.key_must_exist(conf_dict, entry, key)
        if not NetworkProfilesValidation.val_is_str(conf_dict[entry], key):
            NetworkProfilesValidation.err_not_str(entry, key)

    @staticmethod
    def must_be_list(conf_dict, entry, key):
        NetworkProfilesValidation.key_must_exist(conf_dict, entry, key)
        if not NetworkProfilesValidation.val_is_non_empty_list(conf_dict[entry], key):
            NetworkProfilesValidation.err_not_list(entry, key)

    @staticmethod
    def must_be_dict(conf_dict, entry, key):
        NetworkProfilesValidation.key_must_exist(conf_dict, entry, key)
        if not NetworkProfilesValidation.val_is_non_empty_dict(conf_dict[entry], key):
            NetworkProfilesValidation.err_not_dict(entry, key)

    @staticmethod
    def exists_as_dict(conf_dict, entry, key):
        if not NetworkProfilesValidation.key_exists(conf_dict[entry], key):
            return False
        if not NetworkProfilesValidation.val_is_non_empty_dict(conf_dict[entry], key):
            NetworkProfilesValidation.err_not_dict(entry, key)
        return True

    @staticmethod
    def exists_as_int(conf_dict, entry, key):
        if not NetworkProfilesValidation.key_exists(conf_dict[entry], key):
            return False
        if not NetworkProfilesValidation.val_is_int(conf_dict[entry], key):
            NetworkProfilesValidation.err_not_int(entry, key)
        return True

    @staticmethod
    def are_overlapping(ranges1, ranges2):
        for range1 in ranges1:
            for range2 in ranges2:
                if not (range1[0] > range2[1] or range1[1] < range2[0]):
                    return True
        return False

    def __init__(self):
        cmvalidator.CMValidator.__init__(self)
        self.conf = None
        self.networking = None

    def get_subscription_info(self):
        return self.SUBSCRIPTION

    def validate_set(self, props):
        if not self.is_dict(props):
            self.err_input_not_dict()

        if not (self.key_exists(props, self.DOMAIN) or
                self.key_exists(props, self.NETWORKING)):
            self.err_missing(self.INPUT_ERR_CONTEXT,
                             '{} or {}'.format(self.DOMAIN, self.NETWORKING))

        if self.key_exists(props, self.DOMAIN):
            if not props[self.DOMAIN]:
                self.err_not_dict(self.INPUT_ERR_CONTEXT, self.DOMAIN)
            self.conf = json.loads(props[self.DOMAIN])
        else:
            self.conf = json.loads(self.get_plugin_client().get_property(self.DOMAIN))

        if not self.is_non_empty_dict(self.conf):
            self.err_not_dict(self.INPUT_ERR_CONTEXT, self.DOMAIN)

        if self.key_exists(props, self.NETWORKING):
            if not props[self.NETWORKING]:
                self.err_not_dict(self.INPUT_ERR_CONTEXT, self.NETWORKING)
            self.networking = json.loads(props[self.NETWORKING])
        else:
            self.networking = json.loads(self.get_plugin_client().get_property(self.NETWORKING))

        if not self.is_non_empty_dict(self.networking):
            self.err_not_dict(self.INPUT_ERR_CONTEXT, self.NETWORKING)

        self.validate()

    def validate(self):
        for profile_name in self.conf:
            if not self.val_is_non_empty_dict(self.conf, profile_name):
                self.err_not_dict(self.DOMAIN, profile_name)
            self.validate_network_profile(profile_name)

    def validate_network_profile(self, profile_name):
        self.validate_interface_net_mapping(profile_name)
        self.validate_bonding_interfaces(profile_name)
        self.validate_bonding_options(profile_name)
        self.validate_provider_net_ifaces(profile_name)
        self.validate_network_integrity(profile_name)
        self.validate_sriov_provider_networks(profile_name)
        self.validate_provider_networks(profile_name)

    def validate_interface_net_mapping(self, profile_name):
        self.must_be_dict(self.conf, profile_name, self.INTERFACE_NET_MAPPING)
        networks = []
        for iface in self.conf[profile_name][self.INTERFACE_NET_MAPPING]:
            self.validate_iface_name(self.INTERFACE_NET_MAPPING, iface)
            self.validate_not_vlan(self.INTERFACE_NET_MAPPING, iface)
            self.must_be_list(self.conf[profile_name], self.INTERFACE_NET_MAPPING, iface)
            iface_nets = self.conf[profile_name][self.INTERFACE_NET_MAPPING][iface]
            self.validate_used_infra_networks_defined(iface_nets)
            for domain in self.get_network_domains(iface_nets):
                self.validate_untagged_infra_integrity(iface_nets, iface, profile_name, domain)
            networks.extend(iface_nets)
        self.validate_networks_mapped_only_once(profile_name, networks)

    def validate_used_infra_networks_defined(self, networks):
        for net in networks:
            if not self.key_exists(self.networking, net):
                self.err_missing(self.NETWORKING, net)
            self.must_be_dict(self.networking, net, self.NETWORK_DOMAINS)
            for domain in self.networking[net][self.NETWORK_DOMAINS]:
                self.must_be_dict(self.networking[net], self.NETWORK_DOMAINS, domain)

    def get_network_domains(self, networks):
        domains = set()
        for net in networks:
            domains.update(self.networking[net][self.NETWORK_DOMAINS].keys())
        return domains

    def validate_untagged_infra_integrity(self, iface_nets, iface, profile_name, network_domain):
        untagged_infras = []
        untagged_mtu = None
        max_vlan_mtu = 0
        default_mtu = self.get_default_mtu()

        for net in iface_nets:
            if self.key_exists(self.networking[net][self.NETWORK_DOMAINS], network_domain):
                if not self.key_exists(self.networking[net][self.NETWORK_DOMAINS][network_domain],
                                       self.VLAN):
                    untagged_infras.append(net)
                    if self.exists_as_int(self.networking, net, self.MTU):
                        untagged_mtu = self.networking[net][self.MTU]
                    else:
                        untagged_mtu = default_mtu
                else:
                    if self.exists_as_int(self.networking, net, self.MTU):
                        mtu = self.networking[net][self.MTU]
                    else:
                        mtu = default_mtu
                    if mtu > max_vlan_mtu:
                        max_vlan_mtu = mtu

        if not utils.is_virtualized():
            if len(untagged_infras) > 1:
                self.err_untagged_infra_conflict(profile_name, iface)

        if untagged_mtu and untagged_mtu < max_vlan_mtu:
            self.err_untagged_mtu_size(self.NETWORKING, untagged_infras[0])

    def validate_bonding_interfaces(self, profile_name):
        slaves = []
        if self.exists_as_dict(self.conf, profile_name, self.BONDING_INTERFACES):
            for iface in self.conf[profile_name][self.BONDING_INTERFACES]:
                self.validate_iface_name(self.BONDING_INTERFACES, iface)
                if not self.is_bond_iface(iface):
                    self.err_iface_not_bond(self.BONDING_INTERFACES, iface)
                self.must_be_list(self.conf[profile_name], self.BONDING_INTERFACES, iface)
                for slave in self.conf[profile_name][self.BONDING_INTERFACES][iface]:
                    self.validate_bond_slave(iface, slave)
                    slaves.append(slave)
            if len(slaves) != len(set(slaves)):
                self.err_slave_conflict(profile_name)

    def validate_bond_slave(self, iface, slave):
        self.validate_iface_name(iface, slave)
        self.validate_not_vlan(iface, slave)
        self.validate_not_bond(iface, slave)

    def validate_not_bond(self, context, iface):
        if 'bond' in iface:
            self.err_iface_bond(context, iface)

    def validate_bonding_options(self, profile_name):
        self.validate_bonding_option(profile_name, self.LINUX_BONDING_OPTIONS)
        self.validate_bonding_option(profile_name, self.OVS_BONDING_OPTIONS)

    def validate_bonding_option(self, profile_name, options_type):
        if self.key_exists(self.conf[profile_name], options_type):
            if self.conf[profile_name][options_type] not in self.VALID_BONDING_OPTIONS:
                self.err_bonding_options(profile_name, options_type)

    def validate_provider_net_ifaces(self, profile_name):
        if self.exists_as_dict(self.conf, profile_name, self.PROVIDER_NETWORK_INTERFACES):
            types = set()
            networks = []
            for iface in self.conf[profile_name][self.PROVIDER_NETWORK_INTERFACES]:
                self.validate_iface_name(self.PROVIDER_NETWORK_INTERFACES, iface)
                self.validate_not_vlan(self.PROVIDER_NETWORK_INTERFACES, iface)
                provnet_ifaces_conf = self.conf[profile_name][self.PROVIDER_NETWORK_INTERFACES]
                self.validate_provider_net_type(provnet_ifaces_conf, iface)
                self.validate_provider_net_vf_count(provnet_ifaces_conf, iface)
                self.validate_dpdk_max_rx_queues(provnet_ifaces_conf, iface)
                self.validate_no_mtu(provnet_ifaces_conf, iface)
                self.must_be_list(provnet_ifaces_conf, iface, self.PROVIDER_NETWORKS)
                types.add(provnet_ifaces_conf[iface][self.TYPE])
                networks.extend(provnet_ifaces_conf[iface][self.PROVIDER_NETWORKS])
            if self.TYPE_OVS_DPDK in types and self.TYPE_OVS in types:
                self.err_ovs_type_conflict(profile_name)
            if self.TYPE_OVS_DPDK in types and self.TYPE_OVS_OFFLOAD_SRIOV in types:
                self.err_offload_dpdk_conflict(profile_name)
            self.validate_networks_mapped_only_once(profile_name, networks)
            self.validate_used_provider_networks_defined(networks)

    def validate_sriov_provider_networks(self, profile_name):
        if self.exists_as_dict(self.conf, profile_name, self.SRIOV_PROVIDER_NETWORKS):
            networks = self.conf[profile_name][self.SRIOV_PROVIDER_NETWORKS]
            self.validate_used_provider_networks_defined(networks)
            sriov_ifaces = []
            for network in networks:
                if (self.exists_as_int(networks, network, self.VF_COUNT) and
                        networks[network][self.VF_COUNT] < 1):
                    self.err_vf_count(network)
                if (self.key_exists(networks[network], self.TRUSTED) and
                        not self.val_is_bool(networks[network], self.TRUSTED)):
                    self.err_not_bool(network, self.TRUSTED)
                if (self.key_exists(networks[network], self.TYPE) and
                        networks[network][self.TYPE] not in self.VALID_SRIOV_TYPES):
                    self.err_sriov_type(network)
                self.must_be_list(networks, network, self.INTERFACES)
                for iface in networks[network][self.INTERFACES]:
                    sriov_ifaces.append(iface)
                    self.validate_iface_name(network, iface)
                    self.validate_not_vlan(network, iface)
                    self.validate_not_bond(network, iface)
                    self.validate_not_part_of_lacp(self.conf[profile_name], iface)
                    infra_info = self.get_iface_infra_info(self.conf[profile_name], iface)
                    if infra_info is not None:
                        self.validate_shared_sriov_infra(network, iface, infra_info)
                    provider_info = self.get_iface_provider_info(self.conf[profile_name], iface)
                    if provider_info[self.TYPE] == self.TYPE_OVS_DPDK:
                        self.err_dpdk_sriov_conflict(profile_name)
                    if provider_info[self.TYPE] == self.TYPE_OVS_OFFLOAD_SRIOV:
                        self.err_offload_sriov_conflict(profile_name)
                    if provider_info[self.VLAN_RANGES]:
                        self.validate_shared_sriov_provider(network,
                                                            provider_info[self.VLAN_RANGES])
            if len(sriov_ifaces) != len(set(sriov_ifaces)):
                self.err_sriov_iface_conflict()

    def validate_provider_networks(self, profile_name):
        if self.key_exists(self.conf[profile_name], self.PROVIDER_NETWORK_INTERFACES):
            for iface in self.conf[profile_name][self.PROVIDER_NETWORK_INTERFACES]:
                iface_info = self.conf[profile_name][self.PROVIDER_NETWORK_INTERFACES][iface]
                vlan_ranges_list = []
                for network in iface_info[self.PROVIDER_NETWORKS]:
                    vlan_ranges = self.get_vlan_ranges(network)
                    vlan_ranges_list.append(vlan_ranges)
                    infra_info = self.get_iface_infra_info(self.conf[profile_name], iface)
                    if infra_info is not None:
                        if (len(self.conf[profile_name][self.PROVIDER_NETWORK_INTERFACES]) > 1 or
                                len(self.conf[profile_name][self.INTERFACE_NET_MAPPING]) > 1):
                            self.err_single_nic_violation(profile_name)
                        if iface_info[self.TYPE] in self.SINGLE_NIC_UNSUPPORTED_TYPES:
                            self.err_single_nic_provider_type(profile_name, iface_info[self.TYPE])
                        self.validate_shared_infra_provider(network, infra_info, vlan_ranges)
                for idx, ranges1 in enumerate(vlan_ranges_list):
                    for ranges2 in vlan_ranges_list[(idx+1):]:
                        if self.are_overlapping(ranges1, ranges2):
                            self.err_provider_vlan_conflict(iface)

    def validate_not_part_of_lacp(self, profile_conf, iface):
        if self.key_exists(profile_conf, self.PROVIDER_NETWORK_INTERFACES):
            for prov_iface, prov in profile_conf[self.PROVIDER_NETWORK_INTERFACES].iteritems():
                if self.is_bond_iface(prov_iface):
                    if iface in profile_conf[self.BONDING_INTERFACES][prov_iface]:
                        bonding_type = self.OVS_BONDING_OPTIONS \
                            if prov[self.TYPE] != self.TYPE_CAAS else self.LINUX_BONDING_OPTIONS
                        if profile_conf[bonding_type] == self.MODE_LACP:
                            self.err_sriov_lacp_conflict()
                        # part of ovs bonding
                        # do not check linux bonding options even if shared with infra networks
                        return
        for infra_iface in profile_conf[self.INTERFACE_NET_MAPPING]:
            if self.is_bond_iface(infra_iface):
                if iface in profile_conf[self.BONDING_INTERFACES][infra_iface]:
                    if profile_conf[self.LINUX_BONDING_OPTIONS] == self.MODE_LACP:
                        self.err_sriov_lacp_conflict()
                    break

    def validate_shared_sriov_infra(self, sriov_net, iface, infra_info):
        sriov_info = self.get_sriov_info(sriov_net)
        if sriov_info[self.MTU] > infra_info[self.MTU]:
            self.err_sriov_mtu_size(sriov_net, sriov_info[self.MTU], iface, infra_info[self.MTU])
        for vlan_range in sriov_info[self.VLAN_RANGES]:
            for infra_vlan in infra_info[self.VLAN]:
                if not (infra_vlan < vlan_range[0] or infra_vlan > vlan_range[1]):
                    self.err_sriov_infra_vlan_conflict(sriov_net)

    def validate_shared_sriov_provider(self, sriov_net, ovs_vlan_ranges):
        sriov_vlan_ranges = self.get_vlan_ranges(sriov_net)
        if self.are_overlapping(sriov_vlan_ranges, ovs_vlan_ranges):
            self.err_sriov_provider_vlan_conflict(sriov_net)

    def validate_shared_infra_provider(self, provider_net, infra_info, vlan_ranges):
        if infra_info[self.UNTAGGED]:
            self.err_infra_provider_untagged_conflict(provider_net)
        for vlan in infra_info[self.VLAN]:
            for vlan_range in vlan_ranges:
                if not (vlan_range[0] > vlan or vlan_range[1] < vlan):
                    self.err_infra_provider_vlan_conflict(provider_net)

    def get_iface_infra_info(self, profile_conf, iface):
        infra_info = {self.VLAN: [], self.MTU: 0, self.UNTAGGED: False}
        default_mtu = self.get_default_mtu()
        infra_iface = self.get_master_iface(profile_conf, iface)

        if self.key_exists(profile_conf[self.INTERFACE_NET_MAPPING], infra_iface):
            for infra in profile_conf[self.INTERFACE_NET_MAPPING][infra_iface]:
                for domain in self.networking[infra][self.NETWORK_DOMAINS].itervalues():
                    if self.key_exists(domain, self.VLAN):
                        infra_info[self.VLAN].append(domain[self.VLAN])
                    else:
                        infra_info[self.UNTAGGED] = True
                if self.exists_as_int(self.networking, infra, self.MTU):
                    mtu = self.networking[infra][self.MTU]
                else:
                    mtu = default_mtu
                if mtu > infra_info[self.MTU]:
                    infra_info[self.MTU] = mtu

        if infra_info[self.MTU] == 0:
            return None

        return infra_info

    def get_iface_provider_info(self, profile_conf, iface):
        provider_info = {self.TYPE: None, self.VLAN_RANGES: []}
        provider_iface = self.get_master_iface(profile_conf, iface)

        if self.key_exists(profile_conf, self.PROVIDER_NETWORK_INTERFACES):
            if self.key_exists(profile_conf[self.PROVIDER_NETWORK_INTERFACES], provider_iface):
                iface_info = profile_conf[self.PROVIDER_NETWORK_INTERFACES][provider_iface]
                provider_info[self.TYPE] = iface_info[self.TYPE]
                for network in iface_info[self.PROVIDER_NETWORKS]:
                    provider_info[self.VLAN_RANGES].extend(self.get_vlan_ranges(network))

        return provider_info

    def get_master_iface(self, profile_conf, slave_iface):
        if self.key_exists(profile_conf, self.BONDING_INTERFACES):
            for bond in profile_conf[self.BONDING_INTERFACES]:
                if slave_iface in profile_conf[self.BONDING_INTERFACES][bond]:
                    return bond
        return slave_iface

    def get_sriov_info(self, network):
        sriov_info = {self.VLAN_RANGES: []}
        if self.exists_as_int(self.networking[self.PROVIDER_NETWORKS], network, self.MTU):
            sriov_info[self.MTU] = self.networking[self.PROVIDER_NETWORKS][network][self.MTU]
        else:
            sriov_info[self.MTU] = self.get_default_mtu()
        sriov_info[self.VLAN_RANGES] = self.get_vlan_ranges(network)
        return sriov_info

    def get_vlan_ranges(self, network):
        vlan_ranges = []
        networks = self.networking[self.PROVIDER_NETWORKS]
        self.must_be_str(networks, network, self.VLAN_RANGES)
        for vlan_range in networks[network][self.VLAN_RANGES].split(','):
            vids = vlan_range.split(':')
            if len(vids) != 2:
                break
            try:
                start = int(vids[0])
                end = int(vids[1])
            except ValueError:
                break
            if end >= start:
                vlan_ranges.append([start, end])
        return vlan_ranges

    def get_default_mtu(self):
        if (self.key_exists(self.networking, self.MTU) and
                self.val_is_int(self.networking, self.MTU)):
            return self.networking[self.MTU]
        return self.DEFAULT_MTU

    def validate_iface_name(self, context, iface):
        if not isinstance(iface, basestring) or not re.match(self.IFACE_NAME_MATCH, iface):
            self.err_invalid_iface_name(context)
        if len(iface) > self.MAX_IFACE_NAME_LEN:
            self.err_iface_name_len(context)

    def validate_not_vlan(self, context, iface):
        if 'vlan' in iface:
            self.err_iface_vlan(context, iface)

    def validate_provider_net_type(self, provnet_ifaces_conf, iface):
        self.must_be_str(provnet_ifaces_conf, iface, self.TYPE)
        if provnet_ifaces_conf[iface][self.TYPE] not in self.VALID_PROVIDER_TYPES:
            self.err_provnet_type(iface)

    def validate_provider_net_vf_count(self, provnet_ifaces_conf, iface):
        if self.exists_as_int(provnet_ifaces_conf, iface, self.VF_COUNT):
            value = provnet_ifaces_conf[iface][self.VF_COUNT]
            if value < 1:
                self.err_vf_count(iface)

    def validate_dpdk_max_rx_queues(self, provnet_ifaces_conf, iface):
        if self.exists_as_int(provnet_ifaces_conf, iface, self.DPDK_MAX_RX_QUEUES):
            value = provnet_ifaces_conf[iface][self.DPDK_MAX_RX_QUEUES]
            if value < 1:
                self.err_dpdk_max_rx_queues(value)

    def validate_no_mtu(self, provnet_ifaces_conf, iface):
        if self.key_exists(provnet_ifaces_conf[iface], self.MTU):
            self.err_missplaced_mtu(iface)

    def validate_networks_mapped_only_once(self, profile_name, networks):
        prev_net = None
        for net in sorted(networks):
            if net == prev_net:
                self.err_net_mapping_conflict(profile_name, net)
            prev_net = net

    def validate_used_provider_networks_defined(self, networks):
        for net in networks:
            self.key_must_exist(self.networking, self.PROVIDER_NETWORKS, net)

    def validate_network_integrity(self, profile_name):
        provider_ifaces = []
        if self.key_exists(self.conf[profile_name], self.PROVIDER_NETWORK_INTERFACES):
            for iface in self.conf[profile_name][self.PROVIDER_NETWORK_INTERFACES]:
                iface_data = self.conf[profile_name][self.PROVIDER_NETWORK_INTERFACES][iface]
                bonding_type = self.OVS_BONDING_OPTIONS \
                    if iface_data[self.TYPE] != self.TYPE_CAAS else self.LINUX_BONDING_OPTIONS
                self.validate_net_iface_integrity(profile_name, iface, bonding_type)
                provider_ifaces.append(iface)
        for iface in self.conf[profile_name][self.INTERFACE_NET_MAPPING]:
            if iface not in provider_ifaces:
                self.validate_net_iface_integrity(profile_name, iface, self.LINUX_BONDING_OPTIONS)

    def validate_net_iface_integrity(self, profile_name, iface, bonding_type):
        if self.is_bond_iface(iface):
            if (not self.key_exists(self.conf[profile_name], self.BONDING_INTERFACES) or
                    iface not in self.conf[profile_name][self.BONDING_INTERFACES]):
                self.err_missing_bond_def(profile_name, iface)
            self.key_must_exist(self.conf, profile_name, bonding_type)
            self.validate_bond_slave_count(profile_name, iface,
                                           self.conf[profile_name][bonding_type])
        elif self.key_exists(self.conf[profile_name], self.BONDING_INTERFACES):
            for bond in self.conf[profile_name][self.BONDING_INTERFACES]:
                for slave in self.conf[profile_name][self.BONDING_INTERFACES][bond]:
                    if iface == slave:
                        self.err_slave_in_net(profile_name, iface)

    def validate_bond_slave_count(self, profile_name, iface, bonding_mode):
        slave_count = len(self.conf[profile_name][self.BONDING_INTERFACES][iface])
        if bonding_mode == self.MODE_AB and slave_count != 2:
            self.err_ab_slave_count(profile_name, iface)
        elif bonding_mode == self.MODE_LACP and slave_count < 2:
            self.err_lacp_slave_count(profile_name, iface)
