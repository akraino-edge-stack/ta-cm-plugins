# Copyright 2019 Nokia

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
from jinja2 import Environment

from cmframework.apis import cmansibleinventoryconfig
from cmdatahandlers.api import utils


nics_json_txt = """
[ {%- if 'mgmt_mac' in all_vars['hosts'][host] %}
      {%- for mac_members in all_vars['hosts'][host]['mgmt_mac'] %}
          {
          "mac": "{{ mac_members }}"
          }
          {%- if not loop.last %},{%- endif %}
      {%- endfor %}
  {%- else: %}
      {
      "mac": "{{ all_vars['hw_inventory_details'][host]['mgmt_mac'] }}"
      }
  {%- endif %}
]
"""


class zbaremetalnodeinventory(cmansibleinventoryconfig.CMAnsibleInventoryConfigPlugin):
    def __init__(self, confman, inventory, ownhost):
        super(zbaremetalnodeinventory, self).__init__(confman, inventory, ownhost)

    def handle_bootstrapping(self):
        pass

    def handle_provisioning(self):
        self.handle()

    def handle_postconfig(self):
        self.handle()

    def handle_setup(self):
        pass

    @staticmethod
    def _check_host_single_nic(host_network_profile_value, host_interface_net_mapping):
        if 'provider_network_interfaces' in host_network_profile_value:
            host_provider_network_interfaces = host_network_profile_value['provider_network_interfaces']
            if len(host_interface_net_mapping) == 1 and len(host_provider_network_interfaces) == 1:
                if host_interface_net_mapping.keys()[0] == host_provider_network_interfaces.keys()[0]:
                    return True
        return False

    @staticmethod
    def _generate_linux_bonding_options(options):
        mode_mapping = {'active-backup': 'active-backup', 'lacp': '802.3ad'}
        default_options = {'active-backup': 'miimon=100',
                           'lacp': 'lacp_rate=fast miimon=100'}
        for i in options.split():
            key, value = i.split('=')
            if key == 'mode':
                if default_options[value]:
                    return 'mode=' + mode_mapping[value] + ' ' + default_options[value]
                return 'mode=' + mode_mapping[value]

    @staticmethod
    def _generate_ovs_bonding_options(options):
        mode_mapping = {'active-backup': 'active-backup', 'lacp': 'balance-slb',
                        'lacp-layer34': 'balance-tcp'}
        default_options = {'active-backup': '',
                           'lacp': 'lacp=active other_config:lacp-time=fast other_config:bond-detect-mode=carrier',
                           'lacp-layer34': 'lacp=active other_config:lacp-time=fast other_config:bond-detect-mode=carrier'}
        for i in options.split():
            key, value = i.split('=')
            if key == 'mode':
                if default_options[value]:
                    return 'bond_mode=' + mode_mapping[value] + ' ' + default_options[value]
                return 'bond_mode=' + mode_mapping[value]

    @staticmethod
    def _add_static_routes(routes):
        routes_list = []
        for route in routes:
            routes_list.append({"ip_netmask": route["to"], "next_hop": route["via"]})
        return routes_list

    def handle(self):
        usersconf = self.confman.get_users_config_handler()
        hostsconf = self.confman.get_hosts_config_handler()
        admin_user = usersconf.get_admin_user()
        self.add_global_var("home_dir", "/home/" + admin_user)
        all_vars = self.inventory['all']['vars']
        host_locals = self.inventory['_meta']['hostvars']
        nfs_server_ip = host_locals[all_vars['installation_controller']]['networking']['infra_external']['ip']

        for host, hostvars in host_locals.iteritems():
            host_hdd_mapping = hostvars['by_path_disks']
            host_networking = hostvars['networking']
            host_network_profiles_list = all_vars['hosts'][host]['network_profiles']
            host_network_profile_value = all_vars['network_profiles'][host_network_profiles_list[0]]
            host_interface_net_mapping = host_network_profile_value['interface_net_mapping']

            infra_bond = {'in_use': False}
            host_bonding_interfaces = host_network_profile_value.get('bonding_interfaces', {})
            default_mtu = all_vars['networking'].get('mtu', 1500)

            sriov_mtus = {}
            if 'sriov_provider_networks' in host_network_profile_value:
                sriov_nets = host_network_profile_value['sriov_provider_networks']
                prov_infos = host_networking.get('provider_networks', {})
                for net_name, sriov_info in sriov_nets.iteritems():
                    if prov_infos.get(net_name):
                        prov_info = prov_infos[net_name]
                        sriov_mtu = prov_info.get('mtu', default_mtu)
                        for iface in sriov_info['interfaces']:
                            sriov_mtus[iface] = sriov_mtu

            mtu = default_mtu
            if 'mtu' in all_vars['networking']['infra_internal']:
                mtu = all_vars['networking']['infra_internal']['mtu']

            phys_iface_mtu = 1500
            if 'vlan' in host_networking['infra_internal']:
                for iface, infras in host_interface_net_mapping.iteritems():
                    if 'infra_internal' in infras:
                        for infra in infras:
                            tmp_mtu = default_mtu
                            if 'mtu' in all_vars['networking'][infra]:
                                tmp_mtu = all_vars['networking'][infra]['mtu']
                            if infra == 'cloud_tenant':
                                tmp_mtu = tmp_mtu + 50
                            if tmp_mtu > phys_iface_mtu:
                                phys_iface_mtu = tmp_mtu
                        if 'bond' in iface:
                            if host_bonding_interfaces.get(iface):
                                for slave in host_bonding_interfaces[iface]:
                                    if slave in sriov_mtus and sriov_mtus[slave] > phys_iface_mtu:
                                        phys_iface_mtu = sriov_mtus[slave]
                        elif iface in sriov_mtus and sriov_mtus[iface] > phys_iface_mtu:
                            phys_iface_mtu = sriov_mtus[iface]
                        break

            properties = {
                "capabilities": "boot_option:local",
                "cpu_arch": "x86_64",
                "cpus": 8,
                "disk_size": 40,
                "ram": 16384
            }

            power = {
                "provisioning_server": nfs_server_ip,
                "virtmedia_deploy_iso": "file:///opt/images/ironic-deploy.iso",
            }

            if utils.is_virtualized():
                driver = "ssh_virtmedia"
                properties["root_device"] = {"by_path": host_hdd_mapping['os']}
                power["ssh_address"] = all_vars['hosts'][host]['hwmgmt']['address']
                power["ssh_username"] = all_vars['hosts'][host]['hwmgmt']['user']
                power["ipmi_port"] = all_vars['hosts'][host]['vbmc_port']
                power["ipmi_username"] = "admin"
                power["ipmi_password"] = "password"
                power["ssh_key_contents"] = "{{ lookup('file', '/etc/userconfig/id_rsa') }}"
                power["ipmi_address"] = host_locals[all_vars['installation_controller']]['networking']['infra_internal']['ip']
            else:
                driver = "ipmi_virtmedia"
                power["ipmi_address"] = all_vars['hosts'][host]['hwmgmt']['address']
                power["ipmi_password"] = all_vars['hosts'][host]['hwmgmt']['password']
                power["ipmi_username"] = all_vars['hosts'][host]['hwmgmt']['user']
                power["ipmi_priv_level"] = hostsconf.get_hwmgmt_priv_level(host)
                power["product_family"] = all_vars['hw_inventory_details'][host]['product_family']
                power["vendor"] = all_vars['hw_inventory_details'][host]['vendor']

                if host_hdd_mapping['os'] != "/dev/sda":
                    properties["root_device"] = {"by_path": host_hdd_mapping['os']}
                else:
                    properties["root_device"] = {"name": host_hdd_mapping['os']}

            nics_text = Environment().from_string(nics_json_txt).render(all_vars=all_vars, host=host)
            nics_inventory = json.loads(nics_text)

            driver_info = {}
            driver_info["power"] = power
            #####################################################
            network_config = []
            if 'interface' in host_networking['infra_internal']:
                if not self._check_host_single_nic(host_network_profile_value, host_interface_net_mapping):
                    if 'bonding_interfaces' in host_network_profile_value:
                        for net_key, net_value in host_interface_net_mapping.iteritems():
                            bond_contents = {}
                            if "bond" in net_key and "infra_internal" in net_value:
                                members = []
                                for member in host_bonding_interfaces[net_key]:
                                    member_element = {}
                                    if 'bond' in host_networking['infra_internal']['interface']:
                                        member_element["mtu"] = mtu
                                    else:
                                        member_element["mtu"] = phys_iface_mtu
                                    member_element["name"] = member
                                    member_element["type"] = "interface"
                                    member_element["use_dhcp"] = False
                                    members.append(member_element)

                                bond_contents = {
                                    "type": "linux_bond",
                                    "use_dhcp": False
                                }
                                bond_contents["name"] = net_key
                                bond_contents["members"] = members

                                if 'linux_bonding_options' in host_network_profile_value:
                                    bond_contents["bonding_options"] = self._generate_linux_bonding_options(host_network_profile_value['linux_bonding_options'])
                                if 'bond' in host_networking['infra_internal']['interface']:
                                    bond_contents["addresses"] = [{"ip_netmask": "%s/%s" % (host_networking['infra_internal']['ip'], host_networking['infra_internal']['mask'])}]
                                    bond_contents["mtu"] = mtu
                                    if 'routes' in host_networking['infra_internal']:
                                        routes = host_networking['infra_internal']['routes']
                                        bond_contents["routes"] = self._add_static_routes(routes)
                                else:
                                    bond_contents["mtu"] = phys_iface_mtu

                                infra_bond.update({'in_use': True})

                                network_config.append(bond_contents)
                    if 'vlan' in host_networking['infra_internal']:
                        vlan_contents = {
                            "type": "vlan",
                            "use_dhcp": False
                            }
                        vlan_contents["addresses"] = [{"ip_netmask": "%s/%s" % (host_networking['infra_internal']['ip'], host_networking['infra_internal']['mask'])}]
                        vlan_contents["vlan_id"] = host_networking['infra_internal']['vlan']
                        for net_key, net_value in host_interface_net_mapping.iteritems():
                            if "infra_internal" in net_value:
                                vlan_contents["device"] = net_key
                        vlan_contents["mtu"] = mtu
                        if 'routes' in host_networking['infra_internal']:
                            routes = host_networking['infra_internal']['routes']
                            vlan_contents["routes"] = []
                            for route in routes:
                                vlan_contents["routes"].append({"ip_netmask": route["to"], "next_hop": route["via"]})
                        if not infra_bond["in_use"]:
                            vlan_phy_contents = {
                                "type": "interface",
                                "use_dhcp": False,
                                "mtu": phys_iface_mtu
                                }
                            for net_key, net_value in host_interface_net_mapping.iteritems():
                                if "infra_internal" in net_value:
                                    vlan_phy_contents["name"] = net_key
                            network_config.append(vlan_phy_contents)

                        network_config.append(vlan_contents)

                    elif not infra_bond["in_use"]:
                        phy_contents = {
                            "name": host_networking['infra_internal']['interface'],
                            "type": "interface",
                            "mtu": mtu,
                            "use_dhcp": False
                            }
                        phy_contents["addresses"] = [{"ip_netmask": "%s/%s" % (host_networking['infra_internal']['ip'], host_networking['infra_internal']['mask'])}]
                        if 'routes' in host_networking['infra_internal']:
                            routes = host_networking['infra_internal']['routes']
                            phy_contents["routes"] = self._add_static_routes(routes)

                        network_config.append(phy_contents)

                # --> single_nic_setup <-- #
                else:
                    single_nic_contents = {
                        "name": "br-pro0",
                        "type": "ovs_bridge",
                        "members": []
                        }
                    member_elements = {"mtu": phys_iface_mtu, "use_dhcp": False}
                    iface = host_interface_net_mapping.keys()[0]
                    if 'bond' in iface:
                        for bond_iface, bond_value in host_bonding_interfaces.iteritems():
                            if bond_iface == iface:
                                if 'ovs_bonding_options' in host_network_profile_value:
                                    member_elements["ovs_options"] = self._generate_ovs_bonding_options(host_network_profile_value['ovs_bonding_options'])
                                member_elements["name"] = iface
                                member_elements["type"] = "ovs_bond"
                                member_elements["members"] = []
                                for member in bond_value:
                                    ovs_bond_member = {
                                        "name": member,
                                        "type": "interface",
                                        "mtu": phys_iface_mtu,
                                        "use_dhcp": False
                                        }
                                    member_elements["members"].append(ovs_bond_member)
                            single_nic_contents["members"].append(member_elements)
                    else:
                        member_elements["name"] = iface
                        member_elements["type"] = "interface"
                        single_nic_contents["members"].append(member_elements)

                    infra_elements = {}
                    infra = host_networking['infra_internal']
                    infra_elements["use_dhcp"] = False
                    infra_elements["type"] = "vlan"
                    infra_elements["vlan_id"] = infra['vlan']
                    infra_elements["mtu"] = mtu
                    infra_elements["addresses"] = [{"ip_netmask": "%s/%s" % (infra['ip'], infra['mask'])}]
                    if 'routes' in infra:
                        routes = infra['routes']
                        infra_elements["routes"] = self._add_static_routes(routes)

                    single_nic_contents["members"].append(infra_elements)
                    network_config.append(single_nic_contents)
            #####################################################
            driver_info["power"]["os_net_config"] = {"network_config": network_config}

            ironic_node_details = {
                "name": host,
                "driver": driver,
                "network_interface": "noop",
                "nics": nics_inventory,
                "properties": properties,
                "driver_info": driver_info
            }
            self.add_host_var(host, 'ironic_node_details', ironic_node_details)
