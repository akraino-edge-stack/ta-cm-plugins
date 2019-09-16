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
from netaddr import IPNetwork

from cmdatahandlers.api import validation
from cmframework.apis import cmvalidator


class NetworkingValidation(cmvalidator.CMValidator):
    SUBSCRIPTION = r'^cloud\.networking$'
    DOMAIN = 'cloud.networking'

    MAX_MTU = 9000
    MIN_MTU = 1280
    MIN_VLAN = 2
    MAX_VLAN = 4094
    MAX_PROVNET_LEN = 64
    MAX_DNS = 2
    PROVNET_NAME_MATCH = r'^[a-zA-Z][\da-zA-Z-_]+[\da-zA-Z]$'
    NET_DOMAIN_MATCH = PROVNET_NAME_MATCH
    MAX_NET_DOMAIN_LEN = MAX_PROVNET_LEN
    DEFAULT_ROUTE_DEST = '0.0.0.0/0'

    NETWORK_DOMAINS = 'network_domains'
    INFRA_EXTERNAL = 'infra_external'
    INFRA_INTERNAL = 'infra_internal'
    INFRA_STORAGE_CLUSTER = 'infra_storage_cluster'
    CAAS_OAM = 'caas_oam'
    INFRA_NETWORKS = [INFRA_EXTERNAL,
                      INFRA_INTERNAL,
                      INFRA_STORAGE_CLUSTER,
                      CAAS_OAM]

    DNS = 'dns'
    MTU = 'mtu'
    VLAN = 'vlan'
    GATEWAY = 'gateway'
    CIDR = 'cidr'
    IP_START = 'ip_range_start'
    IP_END = 'ip_range_end'
    ROUTES = 'routes'
    TO = 'to'
    VIA = 'via'

    PROVIDER_NETWORKS = 'provider_networks'
    VLAN_RANGES = 'vlan_ranges'
    SHARED = 'shared'

    INPUT_ERR_CONTEXT = 'validate_set() input'
    ERR_INPUT_NOT_DICT = 'Invalid %s, not a dictionary' % INPUT_ERR_CONTEXT

    ERR_MISSING = 'Missing {1} configuration in {0}'
    ERR_NOT_DICT = 'Invalid {1} value in {0}: Empty or not a dictionary'
    ERR_NOT_LIST = 'Invalid {1} value in {0}: Empty, contains duplicates or not a list'
    ERR_NOT_STR = 'Invalid {1} value in {0}: Not a string'
    ERR_NOT_INT = 'Invalid {1} value in {0}: Not an integer'
    ERR_NOT_BOOL = 'Invalid {1} value in {0}: Not a boolean value'

    ERR_MTU = 'Invalid {} mtu: Not in range %i - %i' % (MIN_MTU, MAX_MTU)
    ERR_VLAN = 'Invalid {} vlan: Not in range %i - %i' % (MIN_VLAN, MAX_VLAN)
    ERR_DUPLICATE_INFRA_VLAN = 'Same VLAN ID {} used for multiple infra networks'
    ERR_CIDRS_OVERLAPPING = 'Network CIDR values {} and {} are overlapping'
    ERR_GW_NOT_SUPPORTED = 'Gateway address not supported for {}'
    ERR_INVALID_ROUTES = 'Invalid static routes format for {0} {1}'
    ERR_DEFAULT_ROUTE = 'Default route not supported for {0} {1}'

    ERR_VLAN_RANGES_FORMAT = 'Invalid {} vlan_ranges format'
    ERR_VLAN_RANGES_OVERLAPPING = 'Provider network vlan ranges {} and {} are overlapping'

    ERR_INVALID_PROVNET_NAME = 'Invalid provider network name'
    ERR_PROVNET_LEN = 'Too long provider network name, max %s chars' % MAX_PROVNET_LEN
    ERR_SHARED_NETWORKS = 'Only one provider network can be configured as shared'

    ERR_INVALID_NET_DOMAIN_NAME = 'Invalid network domain name'
    ERR_NET_DOMAIN_LEN = 'Too long network domain name, max %s chars' % MAX_NET_DOMAIN_LEN

    ERR_TOO_MANY_DNS = 'Too many DNS server IP addresses, max %i supported' % MAX_DNS

    ERR_MTU_INSIDE_NETWORK_DOMAIN = 'Missplaced MTU inside {} network domain {}'

    @staticmethod
    def err_input_not_dict():
        raise validation.ValidationError(NetworkingValidation.ERR_INPUT_NOT_DICT)

    @staticmethod
    def err_missing(context, key):
        raise validation.ValidationError(NetworkingValidation.ERR_MISSING.format(context, key))

    @staticmethod
    def err_not_dict(context, key):
        raise validation.ValidationError(NetworkingValidation.ERR_NOT_DICT.format(context, key))

    @staticmethod
    def err_not_list(context, key):
        raise validation.ValidationError(NetworkingValidation.ERR_NOT_LIST.format(context, key))

    @staticmethod
    def err_not_str(context, key):
        raise validation.ValidationError(NetworkingValidation.ERR_NOT_STR.format(context, key))

    @staticmethod
    def err_not_int(context, key):
        raise validation.ValidationError(NetworkingValidation.ERR_NOT_INT.format(context, key))

    @staticmethod
    def err_not_bool(context, key):
        raise validation.ValidationError(NetworkingValidation.ERR_NOT_BOOL.format(context, key))

    @staticmethod
    def err_mtu(context):
        raise validation.ValidationError(NetworkingValidation.ERR_MTU.format(context))

    @staticmethod
    def err_vlan(context):
        raise validation.ValidationError(NetworkingValidation.ERR_VLAN.format(context))

    @staticmethod
    def err_duplicate_vlan(vid):
        raise validation.ValidationError(NetworkingValidation.ERR_DUPLICATE_INFRA_VLAN.format(vid))

    @staticmethod
    def err_vlan_ranges_format(provnet):
        err = NetworkingValidation.ERR_VLAN_RANGES_FORMAT.format(provnet)
        raise validation.ValidationError(err)

    @staticmethod
    def err_vlan_ranges_overlapping(range1, range2):
        ranges = sorted([range1, range2])
        err = NetworkingValidation.ERR_VLAN_RANGES_OVERLAPPING.format(ranges[0], ranges[1])
        raise validation.ValidationError(err)

    @staticmethod
    def err_invalid_provnet_name():
        raise validation.ValidationError(NetworkingValidation.ERR_INVALID_PROVNET_NAME)

    @staticmethod
    def err_provnet_len():
        raise validation.ValidationError(NetworkingValidation.ERR_PROVNET_LEN)

    @staticmethod
    def err_invalid_net_domain_name():
        raise validation.ValidationError(NetworkingValidation.ERR_INVALID_NET_DOMAIN_NAME)

    @staticmethod
    def err_net_domain_len():
        raise validation.ValidationError(NetworkingValidation.ERR_NET_DOMAIN_LEN)

    @staticmethod
    def err_cidrs_overlapping(cidr1, cidr2):
        cidrs = sorted([cidr1, cidr2])
        err = NetworkingValidation.ERR_CIDRS_OVERLAPPING.format(cidrs[0], cidrs[1])
        raise validation.ValidationError(err)

    @staticmethod
    def err_gw_not_supported(network):
        raise validation.ValidationError(NetworkingValidation.ERR_GW_NOT_SUPPORTED.format(network))

    @staticmethod
    def err_invalid_routes(network, domain):
        err = NetworkingValidation.ERR_INVALID_ROUTES.format(network, domain)
        raise validation.ValidationError(err)

    @staticmethod
    def err_default_route(network, domain):
        err = NetworkingValidation.ERR_DEFAULT_ROUTE.format(network, domain)
        raise validation.ValidationError(err)

    @staticmethod
    def err_too_many_dns():
        raise validation.ValidationError(NetworkingValidation.ERR_TOO_MANY_DNS)

    @staticmethod
    def err_shared_networks():
        raise validation.ValidationError(NetworkingValidation.ERR_SHARED_NETWORKS)

    @staticmethod
    def err_mtu_inside_network_domain(infra, domain):
        err = NetworkingValidation.ERR_MTU_INSIDE_NETWORK_DOMAIN.format(infra, domain)
        raise validation.ValidationError(err)

    @staticmethod
    def is_dict(conf):
        return isinstance(conf, dict)

    @staticmethod
    def key_exists(conf_dict, key):
        return key in conf_dict

    @staticmethod
    def val_is_str(conf_dict, key):
        return isinstance(conf_dict[key], basestring)

    @staticmethod
    def val_is_list(conf_dict, key):
        return isinstance(conf_dict[key], list)

    @staticmethod
    def val_is_non_empty_list(conf_dict, key):
        return (isinstance(conf_dict[key], list) and
                len(conf_dict[key]) > 0 and
                len(conf_dict[key]) == len(set(conf_dict[key])))

    @staticmethod
    def val_is_non_empty_dict(conf_dict, key):
        return isinstance(conf_dict[key], dict) and len(conf_dict[key]) > 0

    @staticmethod
    def val_is_int(conf_dict, key):
        return isinstance(conf_dict[key], (int, long))

    @staticmethod
    def val_is_bool(conf_dict, key):
        return isinstance(conf_dict[key], bool)

    @staticmethod
    def key_must_exist(conf_dict, entry, key):
        if not NetworkingValidation.key_exists(conf_dict[entry], key):
            NetworkingValidation.err_missing(entry, key)

    @staticmethod
    def must_be_str(conf_dict, entry, key):
        NetworkingValidation.key_must_exist(conf_dict, entry, key)
        if not NetworkingValidation.val_is_str(conf_dict[entry], key):
            NetworkingValidation.err_not_str(entry, key)

    @staticmethod
    def must_be_list(conf_dict, entry, key):
        NetworkingValidation.key_must_exist(conf_dict, entry, key)
        if not NetworkingValidation.val_is_non_empty_list(conf_dict[entry], key):
            NetworkingValidation.err_not_list(entry, key)

    @staticmethod
    def must_be_dict(conf_dict, entry, key):
        NetworkingValidation.key_must_exist(conf_dict, entry, key)
        if not NetworkingValidation.val_is_non_empty_dict(conf_dict[entry], key):
            NetworkingValidation.err_not_dict(entry, key)

    @staticmethod
    def exists_as_dict(conf_dict, entry, key):
        if not NetworkingValidation.key_exists(conf_dict[entry], key):
            return False
        if not NetworkingValidation.val_is_non_empty_dict(conf_dict[entry], key):
            NetworkingValidation.err_not_dict(entry, key)
        return True

    @staticmethod
    def exists_as_int(conf_dict, entry, key):
        if not NetworkingValidation.key_exists(conf_dict[entry], key):
            return False
        if not NetworkingValidation.val_is_int(conf_dict[entry], key):
            NetworkingValidation.err_not_int(entry, key)
        return True

    @staticmethod
    def exists_as_bool(conf_dict, entry, key):
        if not NetworkingValidation.key_exists(conf_dict[entry], key):
            return False
        if not NetworkingValidation.val_is_bool(conf_dict[entry], key):
            NetworkingValidation.err_not_bool(entry, key)
        return True

    def __init__(self):
        cmvalidator.CMValidator.__init__(self)
        self.utils = validation.ValidationUtils()
        self.conf = None
        self.net_conf = None

    def get_subscription_info(self):
        return self.SUBSCRIPTION

    def validate_set(self, props):
        self.prepare_validate(props)
        self.validate()

    def prepare_validate(self, props):
        if not self.is_dict(props):
            self.err_input_not_dict()

        if not self.key_exists(props, self.DOMAIN):
            self.err_missing(self.INPUT_ERR_CONTEXT, self.DOMAIN)

        self.net_conf = json.loads(props[self.DOMAIN])
        self.conf = {self.DOMAIN: self.net_conf}

        if not self.val_is_non_empty_dict(self.conf, self.DOMAIN):
            self.err_not_dict(self.INPUT_ERR_CONTEXT, self.DOMAIN)

    def validate(self):
        self.validate_dns()
        self.validate_default_mtu()
        self.validate_infra_networks()
        self.validate_provider_networks()
        self.validate_no_overlapping_cidrs()

    def validate_dns(self):
        self.must_be_list(self.conf, self.DOMAIN, self.DNS)
        for server in self.net_conf[self.DNS]:
            self.utils.validate_ip_address(server)
        if len(self.net_conf[self.DNS]) > self.MAX_DNS:
            self.err_too_many_dns()

    def validate_default_mtu(self):
        self.validate_mtu(self.conf, self.DOMAIN)

    def validate_infra_networks(self):
        self.validate_infra_internal()
        self.validate_infra_external()
        self.validate_infra_storage_cluster()
        self.validate_caas_oam()
        self.validate_no_duplicate_infra_vlans()

    def validate_infra_internal(self):
        self.validate_network_exists(self.INFRA_INTERNAL)
        self.validate_infra_network(self.INFRA_INTERNAL)
        self.validate_no_gateway(self.INFRA_INTERNAL)

    def validate_infra_external(self):
        self.validate_network_exists(self.INFRA_EXTERNAL)
        self.validate_infra_network(self.INFRA_EXTERNAL)
        self.validate_gateway(self.INFRA_EXTERNAL)

    def validate_infra_storage_cluster(self):
        if self.network_exists(self.INFRA_STORAGE_CLUSTER):
            self.validate_network_domains(self.INFRA_STORAGE_CLUSTER)
            self.validate_infra_network(self.INFRA_STORAGE_CLUSTER)
            self.validate_no_gateway(self.INFRA_STORAGE_CLUSTER)

    def validate_caas_oam(self):
        self.validate_network_exists(self.CAAS_OAM)
        self.validate_infra_network(self.CAAS_OAM)
        self.validate_gateway(self.CAAS_OAM)

    def validate_infra_network(self, network, vlan_must_exist=False):
        self.validate_mtu(self.net_conf, network)
        self.validate_cidr(network)
        self.validate_vlan(network, vlan_must_exist)
        self.validate_ip_range(network)
        self.validate_routes(network)
        self.validate_no_mtu_inside_network_domain(network)

    def validate_no_duplicate_infra_vlans(self):
        domvids = {}
        for network in self.INFRA_NETWORKS:
            if self.key_exists(self.net_conf, network):
                for domain, domain_conf in self.net_conf[network][self.NETWORK_DOMAINS].iteritems():
                    if self.key_exists(domain_conf, self.VLAN):
                        if domain not in domvids:
                            domvids[domain] = []
                        domvids[domain].append(domain_conf[self.VLAN])
        for vids in domvids.itervalues():
            prev_vid = 0
            for vid in sorted(vids):
                if vid == prev_vid:
                    self.err_duplicate_vlan(vid)
                prev_vid = vid

    def validate_no_overlapping_cidrs(self):
        cidrs = []
        for network in self.INFRA_NETWORKS:
            if self.key_exists(self.net_conf, network):
                for domain_conf in self.net_conf[network][self.NETWORK_DOMAINS].itervalues():
                    cidrs.append(IPNetwork(domain_conf[self.CIDR]))
        for idx, cidr1 in enumerate(cidrs):
            for cidr2 in cidrs[(idx+1):]:
                if not (cidr1[0] > cidr2[-1] or cidr1[-1] < cidr2[0]):
                    self.err_cidrs_overlapping(str(cidr1), str(cidr2))

    def validate_ip_range(self, network):
        domains = self.net_conf[network][self.NETWORK_DOMAINS]
        for domain in domains:
            ip_start = self.get_ip_range_start(domains, domain)
            ip_end = self.get_ip_range_end(domains, domain)
            self.utils.validate_ip_range(ip_start, ip_end)

    def get_ip_range_start(self, domains, domain):
        if self.key_exists(domains[domain], self.IP_START):
            self.validate_ip_range_limiter(domains, domain, self.IP_START)
            return domains[domain][self.IP_START]
        return str(IPNetwork(domains[domain][self.CIDR])[1])

    def get_ip_range_end(self, domains, domain):
        if self.key_exists(domains[domain], self.IP_END):
            self.validate_ip_range_limiter(domains, domain, self.IP_END)
            return domains[domain][self.IP_END]
        return str(IPNetwork(domains[domain][self.CIDR])[-2])

    def validate_ip_range_limiter(self, domains, domain, key):
        self.must_be_str(domains, domain, key)
        self.utils.validate_ip_address(domains[domain][key])
        self.utils.validate_ip_in_subnet(domains[domain][key],
                                         domains[domain][self.CIDR])

    def validate_provider_networks(self):
        if self.network_exists(self.PROVIDER_NETWORKS):
            for netname in self.net_conf[self.PROVIDER_NETWORKS]:
                self.validate_providernet(netname)
            self.validate_shared_provider_network(self.net_conf[self.PROVIDER_NETWORKS])

    def validate_providernet(self, netname):
        self.validate_providernet_name(netname)
        self.must_be_dict(self.net_conf, self.PROVIDER_NETWORKS, netname)
        self.validate_mtu(self.net_conf[self.PROVIDER_NETWORKS], netname)
        self.validate_vlan_ranges(self.net_conf[self.PROVIDER_NETWORKS], netname)

    def validate_shared_provider_network(self, provider_conf):
        shared_counter = 0
        for netname in provider_conf:
            if self.exists_as_bool(provider_conf, netname, self.SHARED):
                if provider_conf[netname][self.SHARED] is True:
                    shared_counter += 1
        if shared_counter > 1:
            self.err_shared_networks()

    def validate_mtu(self, conf, network):
        if self.exists_as_int(conf, network, self.MTU):
            mtu = conf[network][self.MTU]
            if mtu < self.MIN_MTU or mtu > self.MAX_MTU:
                self.err_mtu(network)

    def validate_no_mtu_inside_network_domain(self, network):
        domains = self.net_conf[network][self.NETWORK_DOMAINS]
        for domain in domains:
            if self.key_exists(domains[domain], self.MTU):
                self.err_mtu_inside_network_domain(network, domain)

    def validate_vlan(self, network, must_exist=False):
        domains = self.net_conf[network][self.NETWORK_DOMAINS]
        for domain in domains:
            if must_exist and not self.key_exists(domains[domain], self.VLAN):
                self.err_missing(network, self.VLAN)
            if self.exists_as_int(domains, domain, self.VLAN):
                self.validate_vlan_id(network, domains[domain][self.VLAN])

    def validate_network_exists(self, network):
        self.must_be_dict(self.conf, self.DOMAIN, network)
        self.validate_network_domains(network)

    def validate_network_domains(self, network):
        self.must_be_dict(self.net_conf, network, self.NETWORK_DOMAINS)
        for domain in self.net_conf[network][self.NETWORK_DOMAINS]:
            self.validate_net_domain_name(domain)

    def validate_net_domain_name(self, domain_name):
        if (not isinstance(domain_name, basestring) or
                not re.match(self.NET_DOMAIN_MATCH, domain_name)):
            self.err_invalid_net_domain_name()
        if len(domain_name) > self.MAX_NET_DOMAIN_LEN:
            self.err_net_domain_len()

    def network_exists(self, network):
        return self.exists_as_dict(self.conf, self.DOMAIN, network)

    def validate_cidr(self, network):
        domains = self.net_conf[network][self.NETWORK_DOMAINS]
        for domain in domains:
            self.must_be_str(domains, domain, self.CIDR)
            self.utils.validate_subnet_address(domains[domain][self.CIDR])

    def validate_gateway(self, network):
        domains = self.net_conf[network][self.NETWORK_DOMAINS]
        for domain in domains:
            self.must_be_str(domains, domain, self.GATEWAY)
            self.utils.validate_ip_address(domains[domain][self.GATEWAY])
            self.utils.validate_ip_in_subnet(domains[domain][self.GATEWAY],
                                             domains[domain][self.CIDR])
            self.utils.validate_ip_not_in_range(domains[domain][self.GATEWAY],
                                                self.get_ip_range_start(domains, domain),
                                                self.get_ip_range_end(domains, domain))

    def validate_no_gateway(self, network):
        for domain_conf in self.net_conf[network][self.NETWORK_DOMAINS].itervalues():
            if self.key_exists(domain_conf, self.GATEWAY):
                self.err_gw_not_supported(network)

    def validate_routes(self, network):
        domains = self.net_conf[network][self.NETWORK_DOMAINS]
        for domain in domains:
            if self.key_exists(domains[domain], self.ROUTES):
                if (not self.val_is_list(domains[domain], self.ROUTES) or
                        not domains[domain][self.ROUTES]):
                    self.err_invalid_routes(network, domain)
                for route in domains[domain][self.ROUTES]:
                    self.validate_route(network, domain, route)
                    self.utils.validate_ip_in_subnet(route[self.VIA],
                                                     domains[domain][self.CIDR])
                    self.utils.validate_ip_not_in_range(route[self.VIA],
                                                        self.get_ip_range_start(domains, domain),
                                                        self.get_ip_range_end(domains, domain))

    def validate_route(self, network, domain, route):
        if (not self.is_dict(route) or
                self.TO not in route or
                self.VIA not in route or
                not self.val_is_str(route, self.TO) or
                not self.val_is_str(route, self.VIA)):
            self.err_invalid_routes(network, domain)
        self.utils.validate_subnet_address(route[self.TO])
        self.utils.validate_ip_address(route[self.VIA])
        if route[self.TO] == self.DEFAULT_ROUTE_DEST:
            self.err_default_route(network, domain)

    def validate_providernet_name(self, netname):
        if not isinstance(netname, basestring) or not re.match(self.PROVNET_NAME_MATCH, netname):
            self.err_invalid_provnet_name()
        if len(netname) > self.MAX_PROVNET_LEN:
            self.err_provnet_len()

    def validate_vlan_ranges(self, provnet_conf, provnet):
        self.must_be_str(provnet_conf, provnet, self.VLAN_RANGES)
        vlan_ranges = []
        for vlan_range in provnet_conf[provnet][self.VLAN_RANGES].split(','):
            vids = vlan_range.split(':')
            if len(vids) != 2:
                self.err_vlan_ranges_format(provnet)
            try:
                start = int(vids[0])
                end = int(vids[1])
            except ValueError:
                self.err_vlan_ranges_format(provnet)
            self.validate_vlan_id(provnet, start)
            self.validate_vlan_id(provnet, end)
            if end < start:
                self.err_vlan_ranges_format(provnet)
            vlan_ranges.append([start, end])
        self.validate_vlan_ranges_not_overlapping(vlan_ranges)

    def validate_vlan_ranges_not_overlapping(self, vlan_ranges):
        for idx, range1 in enumerate(vlan_ranges):
            for range2 in vlan_ranges[(idx+1):]:
                if not (range1[0] > range2[1] or range1[1] < range2[0]):
                    self.err_vlan_ranges_overlapping(range1, range2)

    def validate_vlan_id(self, network, vid):
        if vid < self.MIN_VLAN or vid > self.MAX_VLAN:
            self.err_vlan(network)
