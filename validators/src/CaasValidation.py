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
import re
import base64
import logging
import ipaddr
from cmframework.apis import cmvalidator
from cmdatahandlers.api import validation
from cmdatahandlers.api import configerror


class CaasValidationError(configerror.ConfigError):
    def __init__(self, description):
        configerror.ConfigError.__init__(
            self, 'Validation error in caas_validation: {}'.format(description))


class CaasValidationUtils(object):

    def __init__(self):
        pass

    @staticmethod
    def check_key_in_dict(key, dictionary):
        if key not in dictionary:
            raise CaasValidationError("{} cannot be found in {} ".format(key, dictionary))

    def get_every_key_occurrence(self, var, key):
        if hasattr(var, 'iteritems'):
            for k, v in var.iteritems():
                if k == key:
                    yield v
                if isinstance(v, dict):
                    for result in self.get_every_key_occurrence(v, key):
                        yield result
                elif isinstance(v, list):
                    for d in v:
                        for result in self.get_every_key_occurrence(d, key):
                            yield result

    @staticmethod
    def is_optional_param_present(key, dictionary):
        if key not in dictionary:
            logging.info('{} key is not in the config dictionary, since this is an optional '
                         'parameter, validation is skipped.'.format(key))
            return False
        if not dictionary[key]:
            logging.info('Although {} key is in the config dictionary the correspondig value is '
                         'empty, since this is an optional parametery, '
                         'validation is skipped.'.format(key))
            return False
        return True


class CaasValidation(cmvalidator.CMValidator):
    SUBSCRIPTION = r'^cloud\.caas|cloud\.hosts|cloud\.networking|cloud\.network_profiles$'
    CAAS_DOMAIN = 'cloud.caas'
    HOSTS_DOMAIN = 'cloud.hosts'
    NETW_DOMAIN = 'cloud.networking'
    NETPROF_DOMAIN = 'cloud.network_profiles'

    SERV_PROF = 'service_profiles'
    CAAS_PROFILE_PATTERN = 'caas_master|caas_worker'
    CIDR = 'cidr'

    DOCKER_SIZE_QUOTA = "docker_size_quota"
    DOCKER_SIZE_QUOTA_PATTERN = r"^\d*[G,M,K]$"

    HELM_OP_TIMEOUT = "helm_operation_timeout"

    DOCKER0_CIDR = "docker0_cidr"

    INSTANTIATION_TIMEOUT = "instantiation_timeout"

    ENCRYPTED_CA = "encrypted_ca"
    ENCRYPTED_CA_KEY = "encrypted_ca_key"

    CLUSTER_NETS = 'cluster_networks'
    TENANT_NETS = 'tenant_networks'

    def __init__(self):
        cmvalidator.CMValidator.__init__(self)
        self.validation_utils = validation.ValidationUtils()
        self.conf = None
        self.caas_conf = None
        self.caas_utils = CaasValidationUtils()

    def get_subscription_info(self):
        return self.SUBSCRIPTION

    def validate_set(self, props):
        if not self.is_caas_mandatory(props):
            logging.info("{} not found in {}, caas validation is not needed.".format(
                self.CAAS_PROFILE_PATTERN, self.HOSTS_DOMAIN))
            return
        self.props_pre_check(props)
        self.validate_docker_size_quota()
        self.validate_helm_operation_timeout()
        self.validate_docker0_cidr(props)
        self.validate_instantiation_timeout()
        self.validate_encrypted_ca(self.ENCRYPTED_CA)
        self.validate_encrypted_ca(self.ENCRYPTED_CA_KEY)
        self.validate_networks(props)

    def _get_conf(self, props, domain):
        if props.get(domain):
            conf_str = props[domain]
        else:
            conf_str = self.get_plugin_client().get_property(domain)
        return json.loads(conf_str)

    def is_caas_mandatory(self, props):
        if not isinstance(props, dict):
            raise CaasValidationError('The given input: {} is not a dictionary!'.format(props))
        hosts_conf = self._get_conf(props, self.HOSTS_DOMAIN)
        service_profiles = self.caas_utils.get_every_key_occurrence(hosts_conf, self.SERV_PROF)
        pattern = re.compile(self.CAAS_PROFILE_PATTERN)
        for profile in service_profiles:
            if filter(pattern.match, profile):
                return True
        return False

    def props_pre_check(self, props):
        self.caas_conf = self._get_conf(props, self.CAAS_DOMAIN)
        self.conf = {self.CAAS_DOMAIN: self.caas_conf}
        if not self.caas_conf:
            raise CaasValidationError('{} is an empty dictionary!'.format(self.conf))

    def validate_docker_size_quota(self):
        if not self.caas_utils.is_optional_param_present(self.DOCKER_SIZE_QUOTA, self.caas_conf):
            return
        if not re.match(self.DOCKER_SIZE_QUOTA_PATTERN, self.caas_conf[self.DOCKER_SIZE_QUOTA]):
            raise CaasValidationError(
                '{} is not a valid {}!'.format(self.caas_conf[self.DOCKER_SIZE_QUOTA],
                                               self.DOCKER_SIZE_QUOTA))

    def validate_helm_operation_timeout(self):
        if not self.caas_utils.is_optional_param_present(self.HELM_OP_TIMEOUT, self.caas_conf):
            return
        if not isinstance(self.caas_conf[self.HELM_OP_TIMEOUT], int):
            raise CaasValidationError(
                '{}:{} is not an integer'.format(self.HELM_OP_TIMEOUT,
                                                 self.caas_conf[self.HELM_OP_TIMEOUT]))

    def get_docker0_cidr_netw_obj(self, subnet):
        try:
            return ipaddr.IPNetwork(subnet)
        except ValueError as exc:
            raise CaasValidationError('{} is an invalid subnet address: {}'.format(
                self.DOCKER0_CIDR, exc))

    def check_docker0_cidr_overlaps_with_netw_subnets(self, docker0_cidr, props):
        netw_conf = self._get_conf(props, self.NETW_DOMAIN)
        cidrs = self.caas_utils.get_every_key_occurrence(netw_conf, self.CIDR)
        for cidr in cidrs:
            if docker0_cidr.overlaps(ipaddr.IPNetwork(cidr)):
                raise CaasValidationError(
                    'CIDR configured for {} shall be an unused IP range, '
                    'but it overlaps with {} from {}.'.format(self.DOCKER0_CIDR, cidr,
                                                              self.NETW_DOMAIN))

    def validate_docker0_cidr(self, props):
        if not self.caas_utils.is_optional_param_present(self.DOCKER0_CIDR, self.caas_conf):
            return
        docker0_cidr_obj = self.get_docker0_cidr_netw_obj(self.caas_conf[self.DOCKER0_CIDR])
        self.check_docker0_cidr_overlaps_with_netw_subnets(docker0_cidr_obj, props)

    def validate_instantiation_timeout(self):
        if not self.caas_utils.is_optional_param_present(self.INSTANTIATION_TIMEOUT,
                                                         self.caas_conf):
            return
        if not isinstance(self.caas_conf[self.INSTANTIATION_TIMEOUT], int):
            raise CaasValidationError('{}:{} is not an integer'.format(
                self.INSTANTIATION_TIMEOUT, self.caas_conf[self.INSTANTIATION_TIMEOUT]))

    def validate_encrypted_ca(self, enc_ca):
        self.caas_utils.check_key_in_dict(enc_ca, self.caas_conf)
        enc_ca_str = self.caas_conf[enc_ca][0]
        if not enc_ca_str:
            raise CaasValidationError('{} shall not be empty !'.format(enc_ca))
        try:
            base64.b64decode(enc_ca_str)
        except TypeError as exc:
            raise CaasValidationError('Invalid {}: {}'.format(enc_ca, exc))

    def validate_networks(self, props):
        caas_nets = []
        for nets_key in [self.CLUSTER_NETS, self.TENANT_NETS]:
            if self.caas_utils.is_optional_param_present(nets_key, self.caas_conf):
                if not isinstance(self.caas_conf[nets_key], list):
                    raise CaasValidationError('{} is not a list'.format(nets_key))
                if len(set(self.caas_conf[nets_key])) != len(self.caas_conf[nets_key]):
                    raise CaasValidationError('{} has duplicate entries'.format(nets_key))
                caas_nets.extend(self.caas_conf[nets_key])
        if len(set(caas_nets)) != len(caas_nets):
            raise CaasValidationError('{} and {} must be distinct, but same entries are '
                                      'found from both lists'.format(self.CLUSTER_NETS,
                                                                     self.TENANT_NETS))
        self._validate_homogenous_net_setup(props, caas_nets)

    def _validate_homogenous_net_setup(self, props, caas_nets):
        # Validate homogenous CaaS provider network setup
        # pylint: disable=too-many-locals,too-many-nested-blocks
        hosts_conf = self._get_conf(props, self.HOSTS_DOMAIN)
        netprof_conf = self._get_conf(props, self.NETPROF_DOMAIN)
        net_iface_map = {}
        for net in caas_nets:
            net_iface_map[net] = None
            for host, host_conf in hosts_conf.iteritems():
                # Validate only nodes that can host containerized workloads
                if ('caas_worker' in host_conf[self.SERV_PROF] or
                        ('caas_master' in host_conf[self.SERV_PROF] and
                         'compute' not in host_conf[self.SERV_PROF])):
                    # Validating CaaS network 'net' mapping in 'host'
                    is_caas_network_present = False
                    profiles = host_conf.get('network_profiles')
                    if isinstance(profiles, list) and profiles:
                        net_prof = netprof_conf.get(profiles[0])
                    if net_prof is not None:
                        ifaces = net_prof.get('provider_network_interfaces', {})
                        for iface, data in ifaces.iteritems():
                            net_type = data.get('type')
                            networks = data.get('provider_networks', [])
                            if net in networks and net_type == 'caas':
                                is_caas_network_present = True
                                if net_iface_map[net] is None:
                                    net_iface_map[net] = iface
                                elif net_iface_map[net] != iface:
                                    msg = 'CaaS network {} mapped to interface {} in one host '
                                    msg += 'and interface {} in another host'
                                    raise CaasValidationError(msg.format(net, iface,
                                                                         net_iface_map[net]))
                                break
                    if not is_caas_network_present:
                        raise CaasValidationError('CaaS network {} missing from host {}'
                                                  .format(net, host))
