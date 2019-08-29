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
import socket
from jinja2 import Environment
from cmframework.apis import cmansibleinventoryconfig
from cmframework.apis import cmerror
from cmdatahandlers.api import utils
from cmdatahandlers.api import configerror
from serviceprofiles import profiles

json_text_setup = """
{
    "_meta": {
        "hostvars": {
            "{{ installation_controller }}": {
                "ansible_connection": "local",
                "aio_hostname": "{{ installation_controller }}",
                "bootstrap_host_loopback_cinder": "no",
                "bootstrap_host_loopback_swift": "no",
                "bootstrap_host_loopback_nova": "no",
                "bootstrap_host_data_disk_min_size": 30,
                "bootstrap_env_file": "{{ '{{' }} bootstrap_host_aio_config_path {{ '}}' }}/env.d/baremetal.yml",
                "user_secrets_overrides": {
                    "keystone_auth_admin_password": "{{ general.openstack_password }}"
                },
                "sudo_user": "{{ general.admin }}",
                "sudo_user_password": "{{ general.password }}",
                "sudo_user_authorized_keys": [ {% for key in general.admin_authorized_keys %}"{{ key }}"{% if not loop.last %},{% endif %}{% endfor %} ]
            }
        }
    }
}
"""
json_text = """
{
    "_meta": {
        "hostvars": {
            {% set tenant_network = networkingconf.get_cloud_tenant_network_name() %}
            {% for host in hosts %}
            "{{ host.name }}": {
                "hostname": "{{ host.name }}",
                "management_bridge": "{{ hostsconf.get_host_network_ip_holding_interface(host.name, "infra_internal") }}",
                "is_metal": true,
                "container_address": "{{ host.get_network_ip("infra_internal") }}",
                "container_name": "{{ host.name }}",
                "container_networks": {
                    "management_address": {
                        "address": "{{ host.get_network_ip("infra_internal") }}",
                        "bridge": "{{ host.get_network_ip_holding_interface("infra_internal") }}",
                        "netmask": null,
                        "type": "veth"
                    },
                    {% if tenant_network in hostsconf.get_host_networks(host.name) %}
                    "tunnel_address": {
                        "address": "{{ host.get_network_ip(tenant_network) }}",
                        "bridge": "{{ host.get_network_ip_holding_interface(tenant_network) }}",
                        "netmask": "null",
                        "type": "veth"
                    },
                    {% endif %}
                    "storage_address": {
                        "address": "{{ host.get_network_ip("infra_internal") }}",
                        "bridge": "{{ host.get_network_ip_holding_interface("infra_internal") }}",
                        "netmask": "null",
                        "type": "veth"
                    }
                },
                {% if host.is_performance %}
                "heat_api_threads_max" : {{ host.os_max_threads }},
                "nova_api_threads_max" : {{ host.os_max_threads }},
                "cinder_osapi_volume_workers_max" : {{ host.os_max_threads }},
                "glance_api_threads_max" : {{ host.os_max_threads }},
                "neutron_api_threads_max" : {{ host.os_max_threads }},
                {% endif %}
                "physical_host": "{{ host.name }}",
                {% if host.is_controller %}
                "physical_host_group": "orchestration_hosts"
                {% else %}
                "physical_host_group": "compute_hosts"
                {% endif %}
            } {% if not loop.last %},{% endif %}
            {% endfor %}
        }
    },
    "all": {
        "vars": {
            "installation_controller": "{{ installation_controller }}",
            "is_metal": true,
            "haproxy_glance_api_nodes": ["glance-api"],
            "nova_vncserver_listen": "0.0.0.0",
            "nova_novncproxy_base_url": "{% raw %}{{ nova_novncproxy_base_uri }}/vnc_auto.html{% endraw %}",
            "properties": {
                 "is_metal": true
             },
            {% if not virtual_environment %}
            "virtual_env": false,
            {% else %}
            "virtual_env": true,
            {% endif %}
            "container_cidr": "{{ infra_mgmt.cidr }}",
            "haproxy_whitelist_networks": [ {% for cidr in infra_mgmt.cidrs %}"{{ cidr }}"{%if not loop.last %},{% endif %}{% endfor %} ],
            {% if config_phase == 'postconfig' %}
            "external_lb_vip_address": "{{ has.haproxy.external_vip }}",
            "internal_lb_vip_address": "{{ has.haproxy.internal_vip }}",
            "haproxy_keepalived_external_vip_cird": "{{ has.haproxy.external_vip }}/32",
            "haproxy_keepalived_internal_vip_cidr": "{{ has.haproxy.external_vip }}/32",
            {% else %}
            "external_lb_vip_address": "{{ infra_external.ip }}",
            "internal_lb_vip_address": "{{ infra_mgmt.ip }}",
            "haproxy_keepalived_external_vip_cird": "{{ infra_external.ip }}/32",
            "haproxy_keepalived_internal_vip_cidr": "{{ infra_external.ip }}/32",
            {% endif %}
            {%if config_phase == 'postconfig' %}
            "ironic_standalone_auth_strategy": "keystone",
            "galera_ignore_cluster_state": false,
            {% else %}
            "galera_ignore_cluster_state": true,
            {% endif %}
            "keepalived_ping_address": "{{ infra_external.gateway }}",
            "haproxy_keepalived_external_interface": "{{ infra_external.interface }}",
            "haproxy_keepalived_internal_interface": "{{ infra_mgmt.interface }}",
            "management_bridge": "{{ infra_mgmt.interface }}",
            "ntp_servers": [ {% for server in general.ntp_servers %}"{{ server }}"{%if not loop.last %},{% endif %}{% endfor %} ],
            "openrc_file_dest": "/home/{{ general.admin }}/openrc",
            "openrc_file_owner": "{{ general.admin }}",
            "openrc_file_group": "{{ general.admin }}",
            "openrc_openstack_client_config_dir_dest": "/home/{{ general.admin }}/.config/openstack",
            "openrc_openstack_client_config_dir_owner": "{{ general.admin }}",
            "openrc_openstack_client_config_dir_group": "{{ general.admin }}",
            "openrc_clouds_yml_file_dest": "/home/{{ general.admin }}/.config/openstack/clouds.yaml",
            "openrc_clouds_yml_file_owner": "{{ general.admin }}",
            "openrc_clouds_yml_file_group": "{{ general.admin }}",
            "horizon_images_upload_mode": "legacy",
            "horizon_time_zone": "{{ general.zone }}",
            "horizon_disable_password_reveal": true,
            "nova_cpu_allocation_ratio": "1.0",
            "nova_resume_guests_state_on_host_boot": "True",
            "nova_scheduler_default_filters": "RetryFilter,AvailabilityZoneFilter,RamFilter,ComputeFilter,ComputeCapabilitiesFilter,ImagePropertiesFilter,ServerGroupAntiAffinityFilter,ServerGroupAffinityFilter,AggregateCoreFilter,AggregateDiskFilter,NUMATopologyFilter,AggregateInstanceExtraSpecsFilter,PciPassthroughFilter",
            "cinder_volume_clear": "none",
            "haproxy_ssl_pem": "/etc/ssl/private/certificate.pem",
            "ironic_default_network_interface": "noop",
            "restful_service_port": "61200",
            "auth_server_service_address": "localhost",
            "auth_server_service_port": "62200",
            "aaa_galera_address": "{{ has.haproxy.internal_vip }}",
            {% if not virtual_environment %}
            "nova_cpu_mode": "host-passthrough",
            {% else %}
            "nova_cpu_mode": "host-model",
            {% endif %}
            {% if computes|length == 1 %}
            "single_compute" : true,
            {% else %}
            "single_compute" : false,
            {% endif %}
            {% if management_nodes|length == 1 %}
            "single_management" : true
            {% else %}
            "single_management" : false
            {% endif %}
        }
    },
    "all_containers": {
        "children": [
            "unbound_containers",
            "ceph-osd_containers",
            "orchestration_containers",
            "operator_containers",
            "memcaching_containers",
            "metering-infra_containers",
            "ironic-infra_containers",
            "ceph-mon_containers",
            "storage_containers",
            "ironic-server_containers",
            "mq_containers",
            "shared-infra_containers",
            "compute_containers",
            "storage-infra_containers",
            "haproxy_containers",
            "key-manager_containers",
            "metering-alarm_containers",
            "network_containers",
            "os-infra_containers",
            "image_containers",
            "compute-infra_containers",
            "log_containers",
            "ironic-compute_containers",
            "metering-compute_containers",
            "identity_containers",
            "dashboard_containers",
            "dnsaas_containers",
            "database_containers",
            "metrics_containers",
            "repo-infra_containers"
        ],
        "hosts": []
    },
    "aodh_alarm_evaluator": {
        "children": [],
        "hosts": [{% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %}]
    },
    "aodh_alarm_notifier": {
        "children": [],
        "hosts": [{% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %}]
    },
    "aodh_all": {
        "children": [
            "aodh_alarm_notifier",
            "aodh_api",
            "aodh_alarm_evaluator",
            "aodh_listener"
        ],
        "hosts": []
    },
    "aodh_api": {
        "children": [],
        "hosts": [{% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %}]
    },
    "aodh_container": {
        "hosts": []
    },
    "aodh_listener": {
        "children": [],
        "hosts": [{% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %}]
    },
    "barbican_all": {
        "children": [
            "barbican_api"
        ],
        "hosts": []
    },
    "barbican_api": {
        "children": [],
        "hosts": []
    },
    "barbican_container": {
        "hosts": []
    },
    "openstack_nodes": {
        "children": [ "controller", "compute", "storage" ]
    },
    "caas_nodes": {
        "children": [ "caas_master", "caas_worker" ]
    },
    "baremetal-infra_hosts": {
        "hosts": [ {% if not vnf_embedded_deployment %} "{{ installation_controller }}" {% endif %}]
    },
    "baremetal-nodes": {
        "hosts": [ {% if not vnf_embedded_deployment %}{% for host in hosts %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %}{% endif %} ]
    },
    "baremetal_management_nodes": {
        "hosts": [ {% for host in management_nodes %}{% if not vnf_embedded_deployment %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endif %}{% endfor %} ]
    },
    "ceilometer_agent_central": {
        "children": [],
        "hosts": []
    },
    "ceilometer_agent_compute": {
        "children": [],
        "hosts": []
    },
    "ceilometer_agent_notification": {
        "children": [],
        "hosts": []
    },
    "ceilometer_all": {
        "children": [
            "ceilometer_agent_central",
            "ceilometer_agent_notification",
            "ceilometer_api",
            "ceilometer_collector",
            "ceilometer_agent_compute"
        ],
        "hosts": []
    },
    "ceilometer_api": {
        "children": [],
        "hosts": []
    },
    "ceilometer_api_container": {
        "hosts": []
    },
    "ceilometer_collector": {
        "children": [],
        "hosts": []
    },
    "ceilometer_collector_container": {
        "hosts": []
    },
    {% if storagebackend != 'ceph' %}
    "ceph-mon": {
        "children": [],
        "hosts": []
    },
    "ceph-mon_hosts": {
        "children": [],
        "hosts": []
    },
    "ceph-osd": {
        "children": [],
        "hosts": []
    },
    "ceph-osd_hosts": {
        "children": [],
        "hosts": []
    },
    "ceph-mgr": {
        "children": [],
        "hosts": []
    },
    {% endif %}
    "ceph-mon_container": {
        "hosts": []
    },
    "ceph-mon_containers": {
        "children": [],
        "hosts": []
    },
    "ceph-osd_container": {
        "hosts": []
    },
    "ceph-osd_containers": {
        "children": [],
        "hosts": []
    },
    "ceph_all": {
        "children": [
            "ceph-mon",
            "ceph-osd",
            "ceph-mgr"
        ],
        "hosts": []
    },
    "cinder_all": {
        "children": [
            "cinder_api",
            "cinder_backup",
            "cinder_volume",
            "cinder_scheduler"
        ],
        "hosts": []
    },
    "cinder_api": {
        "children": [],
        {% if storagebackend == 'ceph' %}
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
        {% else %}
        "hosts": [ {% if not caas_only_deployment %}"{{ installation_controller }}"{% endif %} ]
        {% endif %}
    },
    "cinder_api_container": {
        "hosts": []
    },
    "cinder_backup": {
        "children": [],
        {% if storagebackend == 'ceph' %}
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
        {% else %}
        "hosts": [ {% if not caas_only_deployment %}"{{ installation_controller }}"{% endif %} ]
        {% endif %}
    },
    "cinder_scheduler": {
        "children": [],
        {% if storagebackend == 'ceph' %}
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
        {% else %}
        "hosts": [ {% if not caas_only_deployment %}"{{ installation_controller }}"{% endif %} ]
        {% endif %}
    },
    "cinder_scheduler_container": {
        "hosts": []
    },
    "cinder_volume": {
        "children": [],
        {% if storagebackend == 'ceph' %}
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
        {% else %}
        "hosts": [ {% if not caas_only_deployment %}"{{ installation_controller }}"{% endif %} ]
        {% endif %}
    },
    "cinder_volumes_container": {
        "hosts": []
    },
    "compute-infra_all": {
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "compute-infra_containers": {
        "children": [ {% for host in containers %}"{{ host.name }}-host_containers"{% if not loop.last %},{% endif %}{% endfor %} ],
        "hosts": []
    },
    "compute-infra_hosts": {
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "compute_all": {
        "hosts": [ {% for host in computes %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "compute_containers": {
        "children": [ {% for host in computes %}"{{ host.name }}-host_containers"{% if not loop.last %},{% endif %}{% endfor %} ],
        "hosts": []
    },
    "compute_hosts": {
        "hosts": [ {% for host in computes %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "dashboard_all": {
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "dashboard_containers": {
        "children": [ {% for host in controllers %}"{{ host.name }}-host_containers"{% if not loop.last %},{% endif %}{% endfor %} ],
        "hosts": []
    },
    "dashboard_hosts": {
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "database_containers": {
        "children": [],
        "hosts": []
    },
    "database_hosts": {
        "children": [],
        "hosts": []
    },
    "designate_all": {
        "children": [
            "designate_producer",
            "designate_mdns",
            "designate_api",
            "designate_worker",
            "designate_central",
            "designate_sink"
        ],
        "hosts": []
    },
    "designate_api": {
        "children": [],
        "hosts": []
    },
    "designate_central": {
        "children": [],
        "hosts": []
    },
    "designate_container": {
        "hosts": []
    },
    "designate_mdns": {
        "children": [],
        "hosts": []
    },
    "designate_producer": {
        "children": [],
        "hosts": []
    },
    "designate_sink": {
        "children": [],
        "hosts": []
    },
    "designate_worker": {
        "children": [],
        "hosts": []
    },
    "dnsaas_containers": {
        "children": [],
        "hosts": []
    },
    "dnsaas_hosts": {
        "children": [],
        "hosts": []
    },
    "galera": {
        "children": [],
        "hosts": [ {% for host in management_nodes %}{% if not vnf_embedded_deployment %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endif %}{% endfor %} ]
    },
    "galera_all": {
        "children": [
            "galera"
        ],
        "hosts": []
    },
    "galera_container": {
        "hosts": []
    },
    "glance_all": {
        "children": [
            "glance_registry",
            "glance_api"
        ],
        "hosts": []
    },
    "glance_api": {
        "children": [],
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "glance_container": {
        "hosts": []
    },
    "glance_registry": {
        "children": [],
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "gnocchi_all": {
        "children": [
            "gnocchi_api",
            "gnocchi_metricd"
        ],
        "hosts": []
    },
    "gnocchi_api": {
        "children": [],
        "hosts": []
    },
    "gnocchi_container": {
        "hosts": []
    },
    "gnocchi_metricd": {
        "children": [],
        "hosts": []
    },
    {% if config_phase != 'bootstrapping' %}
    "haproxy": {
        "children": [],
        "hosts": [ {% if not vnf_embedded_deployment %}{% for host in management_nodes %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %}{% endif %} ]
    },
    "haproxy_all": {
        "children": [
            "haproxy"
        ],
        "hosts": [ {% if not vnf_embedded_deployment %}{% for host in management_nodes %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %}{% endif %} ]
    },
    "haproxy_container": {
        "hosts": []
    },
    "haproxy_containers": {
        "children": [ {% if not vnf_embedded_deployment %}{% for host in management_nodes %}"{{ host.name }}-host_containers"{% if not loop.last %},{% endif %}{% endfor %}{% endif %} ],
        "hosts": []
    },
    "haproxy_hosts": {
        "hosts": [ {% if not vnf_embedded_deployment %}{% for host in management_nodes %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %}{% endif %} ]
    },
    {% endif %}
    "heat_all": {
        "children": [
            "heat_api",
            "heat_engine",
            "heat_api_cloudwatch",
            "heat_api_cfn"
        ],
        "hosts": []
    },
    "heat_api": {
        "children": [],
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "heat_api_cfn": {
        "children": [],
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "heat_api_cloudwatch": {
        "children": [],
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "heat_apis_container": {
        "hosts": []
    },
    "heat_engine": {
        "children": [],
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "heat_engine_container": {
        "hosts": []
    },
    "horizon": {
        "children": [],
        "hosts": [ {% if not vnf_embedded_deployment %}{% for host in management_nodes %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %}{% endif %} ]
    },
    "horizon_all": {
        "children": [
            "horizon"
        ],
        "hosts": []
    },
    "horizon_container": {
        "hosts": []
    },
    "hosts": {
        "children": [
            "memcaching_hosts",
            "metering-compute_hosts",
            "image_hosts",
            "shared-infra_hosts",
            "storage_hosts",
            "metering-infra_hosts",
            "os-infra_hosts",
            "ironic-server_hosts",
            "key-manager_hosts",
            "ceph-osd_hosts",
            "dnsaas_hosts",
            "network_hosts",
            "haproxy_hosts",
            "mq_hosts",
            "database_hosts",
            "ironic-compute_hosts",
            "metering-alarm_hosts",
            "log_hosts",
            "ceph-mon_hosts",
            "compute_hosts",
            "orchestration_hosts",
            "compute-infra_hosts",
            "identity_hosts",
            "unbound_hosts",
            "ironic-infra_hosts",
            "metrics_hosts",
            "dashboard_hosts",
            "storage-infra_hosts",
            "operator_hosts",
            "repo-infra_hosts"
        ],
        "hosts": []
    },
    "identity_all": {
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "identity_containers": {
        "children": [ {% for host in controllers %}"{{ host.name }}-host_containers"{% if not loop.last %},{% endif %}{% endfor %} ],
        "hosts": []
    },
    "identity_hosts": {
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "image_all": {
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "image_containers": {
        "children": [ {% for host in controllers %}"{{ host.name }}-host_containers"{% if not loop.last %},{% endif %}{% endfor %} ],
        "hosts": []
    },
    "image_hosts": {
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "installation_controller": {
        "hosts": [ "{{ installation_controller }}" ]
    },
    "ironic-compute_all": {
        "hosts": []
    },
    "ironic-compute_containers": {
        "children": [],
        "hosts": []
    },
    "ironic-compute_hosts": {
        "hosts": []
    },
    "ironic-infra_all": {
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "ironic-infra_containers": {
        "children": [ {% for host in controllers %}"{{ host.name }}-host_containers"{% if not loop.last %},{% endif %}{% endfor %} ],
        "hosts": []
    },
    "ironic-infra_hosts": {
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "ironic-server_containers": {
        "children": [],
        "hosts": []
    },
    "ironic-server_hosts": {
        "children": [],
        "hosts": []
    },
    "ironic_all": {
        "children": [
            "ironic_conductor",
            "ironic_api"
        ],
        "hosts": []
    },
    "ironic_api": {
        "children": [],
        "hosts": [ {% for host in management_nodes %}{% if not vnf_embedded_deployment %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endif %}{% endfor %} ]
    },
    "ironic_api_container": {
        "hosts": []
    },
    "ironic_compute": {
        "children": [],
        "hosts": []
    },
    "ironic_compute_container": {
        "hosts": []
    },
    "ironic_conductor": {
        "children": [],
        "hosts": [ {% for host in management_nodes %}{% if not vnf_embedded_deployment %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endif %}{% endfor %} ]
    },
    "ironic_conductor_container": {
        "hosts": []
    },
    "ironic_server": {
        "children": [],
        "hosts": []
    },
    "ironic_server_container": {
        "hosts": []
    },
    "ironic_servers": {
        "children": [
            "ironic_server"
        ],
        "hosts": []
    },
    "key-manager_containers": {
        "children": [],
        "hosts": []
    },
    "key-manager_hosts": {
        "children": [],
        "hosts": []
    },
    "keystone": {
        "children": [],
        "hosts": [ {% for host in management_nodes %}{% if not vnf_embedded_deployment %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endif %}{% endfor %} ]
    },
    "keystone_all": {
        "children": [
            "keystone"
        ],
        "hosts": []
    },
    "keystone_container": {
        "hosts": []
    },
    "log_containers": {
        "children": [],
        "hosts": []
    },
    "log_hosts": {
        "children": [],
        "hosts": []
    },
    "lxc_hosts": {
        "hosts": [ {% for host in hosts %}{% if not vnf_embedded_deployment %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endif %}{% endfor %} ]
    },
    "memcached": {
        "children": [],
        "hosts": [ {% for host in management_nodes %}{% if not vnf_embedded_deployment %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endif %}{% endfor %} ]
    },
    "memcached_all": {
        "children": [
            "memcached"
        ],
        "hosts": []
    },
    "memcached_container": {
        "hosts": []
    },
    "memcaching_containers": {
        "children": [],
        "hosts": []
    },
    "memcaching_hosts": {
        "children": [],
        "hosts": []
    },
    "metering-alarm_containers": {
        "children": [],
        "hosts": []
    },
    "metering-alarm_hosts": {
        "children": [],
        "hosts": []
    },
    "metering-compute_container": {
        "hosts": []
    },
    "metering-compute_containers": {
        "children": [],
        "hosts": []
    },
    "metering-compute_hosts": {
        "children": [],
        "hosts": []
    },
    "metering-infra_containers": {
        "children": [],
        "hosts": []
    },
    "metering-infra_hosts": {
        "children": [],
        "hosts": []
    },
    "metrics_containers": {
        "children": [],
        "hosts": []
    },
    "metrics_hosts": {
        "children": [],
        "hosts": []
    },
    "mq_containers": {
        "children": [],
        "hosts": []
    },
    "mq_hosts": {
        "children": [],
        "hosts": []
    },
    "network_all": {
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "network_containers": {
        "children": [ {% for host in controllers %}"{{ host.name }}-host_containers"{% if not loop.last %},{% endif %}{% endfor %} ],
        "hosts": []
    },
    "network_hosts": {
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "neutron_agent": {
        "children": [],
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "neutron_agents_container": {
        "hosts": []
    },
    "neutron_all": {
        "children": [
            "neutron_agent",
            "neutron_metadata_agent",
            "neutron_linuxbridge_agent",
            "neutron_bgp_dragent",
            "neutron_dhcp_agent",
            "neutron_lbaas_agent",
            "neutron_l3_agent",
            "neutron_metering_agent",
            "neutron_server",
            "neutron_sriov_nic_agent",
            "neutron_openvswitch_agent"
        ],
        "hosts": []
    },
    "neutron_bgp_dragent": {
        "children": [],
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "neutron_dhcp_agent": {
        "children": [],
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "neutron_l3_agent": {
        "children": [],
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "neutron_lbaas_agent": {
        "children": [],
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "neutron_linuxbridge_agent": {
        "children": [],
        "hosts": [ {% for host in neutron_agent_hosts %}{% if not caas_only_deployment %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endif %}{% endfor %} ]
    },
    "neutron_metadata_agent": {
        "children": [],
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "neutron_metering_agent": {
        "children": [],
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "neutron_openvswitch_agent": {
        "children": [],
        "hosts": [ {% for host in neutron_agent_hosts %}{% if not caas_only_deployment %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endif %}{% endfor %} ]
    },
    "neutron_server": {
        "children": [],
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "neutron_server_container": {
        "hosts": []
    },
    "neutron_sriov_nic_agent": {
        "children": [],
        "hosts": [ {% for host in computes %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "nova_all": {
        "children": [
            "nova_console",
            "nova_scheduler",
            "ironic_compute",
            "nova_api_placement",
            "nova_api_metadata",
            "nova_api_os_compute",
            "nova_conductor",
            "nova_compute"
        ],
        "hosts": []
    },
    "nova_api_metadata": {
        "children": [],
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "nova_api_metadata_container": {
        "hosts": []
    },
    "nova_api_os_compute": {
        "children": [],
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "nova_api_os_compute_container": {
        "hosts": []
    },
    "nova_api_placement": {
        "children": [],
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "nova_api_placement_container": {
        "hosts": []
    },
    "nova_compute": {
        "children": [],
        "hosts": [ {% for host in computes %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "nova_compute_container": {
        "hosts": []
    },
    "nova_conductor": {
        "children": [],
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "nova_conductor_container": {
        "hosts": []
    },
    "nova_console": {
        "children": [],
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "nova_console_container": {
        "hosts": []
    },
    "nova_scheduler": {
        "children": [],
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "nova_scheduler_container": {
        "hosts": []
    },
    "operator_containers": {
        "children": [],
        "hosts": []
    },
    "operator_hosts": {
        "children": [],
        "hosts": []
    },
    "orchestration_all": {
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "orchestration_containers": {
        "children": [ {% for host in controllers %}"{{ host.name }}-host_containers"{% if not loop.last %},{% endif %}{% endfor %} ],
        "hosts": []
    },
    "orchestration_hosts": {
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "os-infra_containers": {
        "children": [],
        "hosts": []
    },
    "os-infra_hosts": {
        "children": [],
        "hosts": []
    },
    "pkg_repo": {
        "children": [],
        "hosts": []
    },
    "rabbit_mq_container": {
        "hosts": []
    },
    "rabbitmq": {
        "children": [],
        "hosts": [ {% for host in management_nodes %}{% if not vnf_embedded_deployment %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endif %}{% endfor %} ]
    },
    "rabbitmq_all": {
        "children": [
            "rabbitmq"
        ],
        "hosts": []
    },
    "repo-infra_containers": {
        "children": [],
        "hosts": []
    },
    "repo-infra_hosts": {
        "children": [],
        "hosts": []
    },
    "repo_all": {
        "children": [
            "pkg_repo"
        ],
        "hosts": []
    },
    "repo_container": {
        "hosts": []
    },
    "rsyslog": {
        "children": [],
        "hosts": []
    },
    "rsyslog_all": {
        "children": [
            "rsyslog"
        ],
        "hosts": []
    },
    "rsyslog_container": {
        "hosts": []
    },
    "shared-infra_hosts":
    {
        "hosts": [ {% if not vnf_embedded_deployment %}{% for host in management_nodes %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %}{% endif %} ]
    },
    "storage-infra_all": {
        "hosts": [ {% for host in storages %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "storage-infra_containers": {
        "children": [ {% for host in storages %}"{{ host.name }}-host_containers"{% if not loop.last %},{% endif %}{% endfor %} ],
        "hosts": []
    },
    "storage-infra_hosts": {
        "hosts": [ {% for host in storages %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "storage_all": {
        "hosts": [ {% for host in storages %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "storage_containers": {
        "children": [ {% for host in storages %}"{{ host.name }}-host_containers"{% if not loop.last %},{% endif %}{% endfor %} ],
        "hosts": []
    },
    "storage_hosts": {
        "hosts": [ {% for host in storages %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "unbound": {
        "children": [],
        "hosts": []
    },
    "unbound_all": {
        "children": [
            "unbound"
        ],
        "hosts": []
    },
    "unbound_container": {
        "hosts": []
    },
    "unbound_containers": {
        "children": [],
        "hosts": []
    },
    "unbound_hosts": {
        "children": [],
        "hosts": []
    },
    "utility": {
        "children": [],
        "hosts": [ {% for host in controllers %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
    },
    "utility_all": {
        "children": [
            "utility"
        ],
        "hosts": []
    },
    "utility_container": {
        "hosts": []
    },
    "vnf-nodes": {
        "hosts": [ {% for host in hosts %}{% if vnf_embedded_deployment %} "{{ host.name }}"{% if not loop.last %},{% endif %}{% endif %}{% endfor %} ]
    }
}
"""

class General:
    def __init__(self):
        self.dns_servers = []
        self.ntp_servers = []
        self.zone = None
        self.admin = None
        self.password = None
        self.openstack_password = None
        self.admin_authorized_keys = []

class Network:
    def __init__(self):
        self.name = None
        self.cidr = None
        self.cidrs = set()
        self.vlan = None
        self.gateway = None

class HostNetwork:
    def __init__(self):
        self.network = None
        self.interface = None
        self.ip_holding_interface = None
        self.is_bonding = False
        self.linux_bonding_options = None
        self.members = []
        self.ip = None

class ProviderNetwork:
    def __init__(self):
        self.cidr = None
        self.cidrs = None
        self.interface = None
        self.ip = None
        self.gateway = None

class Host:
    def __init__(self):
        self.name = None
        self.is_controller = False
        self.is_caas_master = False
        self.is_compute = False
        self.is_storage = False
        self.is_management = False
        self.networks = []
        self.hwmgmt_address = None
        self.hwmgmt_password = None
        self.hwmgmt_user = None
        self.hwmgmt_priv_level = 'ADMINISTRATOR'
        self.mgmt_mac = None
        self.is_performance = False
        self.os_max_threads = 16


    def get_network_ip(self, networkname):
        for network in self.networks:
            if network.network.name == networkname:
                return network.ip.split('/')[0]

    def get_network_ip_holding_interface(self, networkname):
        for network in self.networks:
            if network.network.name == networkname:
                return network.ip_holding_interface


class HAProxy:
    def __init__(self):
        self.internal_vip = None
        self.external_vip = None

class HAS:
    def __init__(self):
        self.haproxy = HAProxy()

class openstackinventory(cmansibleinventoryconfig.CMAnsibleInventoryConfigPlugin):
    def __init__(self, confman, inventory, ownhost):
        super(openstackinventory, self).__init__(confman, inventory, ownhost)
        self.networks = []
        self.hosts = []
        self.controllers = []
        self.managements = []
        self.caas_masters = []
        self.computes = []
        self.storages = []
        self.neutron_agent_hosts = set()
        self.has = HAS()
        self.general = General()
        self._init_jinja_environment()
        self.orig_inventory = inventory.copy()


    def handle_bootstrapping(self):
        self.handle('bootstrapping')

    def handle_provisioning(self):
        self.handle('provisioning')

    def handle_postconfig(self):
        self.handle('postconfig')

    def handle_setup(self):
        try:
            ownhostobj = None
            for host in self.hosts:
                if host.name == self.ownhost:
                    ownhostobj = host
                    break
            if not ownhostobj:
                raise cmerror.CMError('Invalid own host configuration %s' % self.ownhost)
            text = Environment().from_string(json_text_setup).render(host=ownhostobj, installation_controller=self.ownhost, general=self.general)

            inventory = json.loads(text)

            #add some variables from the original inventory
            self.inventory.update(inventory)
            self.inventory['all'] = {'hosts': [self.ownhost]}
            self.inventory['all']['vars'] = {}

            setuphosts = {}
            setupnetworking = {}
            setupnetworkprofiles = {}

            if 'hosts' in self.orig_inventory['all']['vars'] and self.ownhost in self.orig_inventory['all']['vars']['hosts']:
                setuphosts = self.orig_inventory['all']['vars']['hosts'][self.ownhost]
            if 'networking' in self.orig_inventory['all']['vars']:
                setupnetworking = self.orig_inventory['all']['vars']['networking']
            if 'network_profiles' in self.orig_inventory['all']['vars']:
                setupnetworkprofiles = self.orig_inventory['all']['vars']['network_profiles']

            if setuphosts:
                self.inventory['all']['vars']['hosts'] = {self.ownhost: setuphosts}
            if setupnetworking:
                self.inventory['all']['vars']['networking'] = setupnetworking
            if setupnetworkprofiles:
                self.inventory['all']['vars']['network_profiles'] = setupnetworkprofiles

            #add networking configuration to own host
            if self.ownhost in self.orig_inventory['_meta']['hostvars'] and 'networking' in self.orig_inventory['_meta']['hostvars'][self.ownhost]:
                self.inventory['_meta']['hostvars'][self.ownhost]['networking'] = self.orig_inventory['_meta']['hostvars'][self.ownhost]['networking']

        except Exception as exp:
            raise cmerror.CMError(str(exp))

    def handle(self, phase):
        try:
            networkingconf = self.confman.get_networking_config_handler()
            hostsconf = self.confman.get_hosts_config_handler()

            infrainternal = networkingconf.get_infra_internal_network_name()
            infraexternal = networkingconf.get_infra_external_network_name()

            installation_controller = socket.gethostname()

            # sort management nodes so that installation_controlle is the first
            modified_list = []
            for entry in self.managements:
                if entry.name == installation_controller:
                    modified_list.append(entry)

            for entry in self.managements:
                if entry.name != installation_controller:
                    modified_list.append(entry)

            self.managements = modified_list

            installation_controller_ip = networkingconf.get_host_ip(installation_controller, infrainternal)
            installation_network_domain = hostsconf.get_host_network_domain(installation_controller)

            virtual_environment = utils.is_virtualized()

            openstackconfig = self.confman.get_openstack_config_handler()
            storagebackend = openstackconfig.get_storage_backend()

            #construct privder netwrks based on the installation controller
            infra_mgmt = ProviderNetwork()
            infra_external = ProviderNetwork()

            host = self._get_host(installation_controller)

            #Installation controller has to be the first one in the controllers list
            #Most of the openstack ansbile modules are executed on first host in the list. This does not work properly.
            if self.controllers:
                self.controllers.remove(host)
                self.controllers.insert(0, host)

            for hostnet in host.networks:
                if hostnet.network.name == infrainternal:
                    infra_mgmt.cidr = hostnet.network.cidr
                    infra_mgmt.cidrs = hostnet.network.cidrs
                    infra_mgmt.interface = hostnet.ip_holding_interface
                    infra_mgmt.ip = networkingconf.get_host_ip(installation_controller, infrainternal)
                elif hostnet.network.name == infraexternal:
                    infra_external.cidr = hostnet.network.cidr
                    infra_external.interface = hostnet.ip_holding_interface
                    infra_external.ip = networkingconf.get_host_ip(installation_controller, infraexternal)
                    infra_external.gateway = networkingconf.get_network_gateway(infraexternal, installation_network_domain)

            caas_conf = self.confman.get_caas_config_handler()

            text = Environment().from_string(json_text).render(hosts=self.hosts, networks=self.networks, general=self.general, has=self.has, virtual_environment=virtual_environment, installation_controller=installation_controller, installation_controller_ip=installation_controller_ip, infra_mgmt=infra_mgmt, infra_external=infra_external, controllers=self.controllers, computes=self.computes, storages=self.storages, neutron_agent_hosts=self.neutron_agent_hosts, config_phase=phase, hostsconf=hostsconf, networkingconf=networkingconf, storagebackend=storagebackend, vnf_embedded_deployment = caas_conf.get_vnf_flag(), caas_only_deployment = caas_conf.get_caas_only(), management_nodes = self.managements)
            #print(text)
            inventory = json.loads(text)

            #process host vars
            for host in inventory['_meta']['hostvars'].keys():
                for var, value in inventory['_meta']['hostvars'][host].iteritems():
                    self.add_host_var(host, var, value)

            #process all vars
            for var, value in inventory['all']['vars'].iteritems():
                self.add_global_var(var, value)

            #process groups
            for var, value in inventory.iteritems():
                if var == '_meta' or var == 'all':
                    continue
                self.inventory[var] = value

            #create a mapping between service-groups and vips to be added to /etc/hosts
            if phase == "postconfig":
                sgvips = {}
                sgvips['config-manager'] = networkingconf.get_internal_vip()
                sgvips['haproxyvip'] = networkingconf.get_internal_vip()
                self.add_global_var('extra_hosts_entries', sgvips)

        except Exception as exp:
            raise cmerror.CMError(str(exp))

    def _is_host_controller(self, host):
        hostsconf = self.confman.get_hosts_config_handler()
        node_service_profiles = hostsconf.get_service_profiles(host)
        controller_profile = profiles.Profiles.get_controller_service_profile()
        for profile in node_service_profiles:
            if profile == controller_profile:
                return True
        return False

    def _is_host_caas_master(self, host):
        hostsconf = self.confman.get_hosts_config_handler()
        node_service_profiles = hostsconf.get_service_profiles(host)
        caas_master_profile = profiles.Profiles.get_caasmaster_service_profile()
        for profile in node_service_profiles:
            if profile == caas_master_profile:
                return True
        return False

    def _is_host_management(self, host):
        hostsconf = self.confman.get_hosts_config_handler()
        node_service_profiles = hostsconf.get_service_profiles(host)
        management_profile = profiles.Profiles.get_management_service_profile()
        for profile in node_service_profiles:
            if profile == management_profile:
                return True
        return False

    def _is_host_compute(self, host):
        hostsconf = self.confman.get_hosts_config_handler()
        node_service_profiles = hostsconf.get_service_profiles(host)
        compute_profile = profiles.Profiles.get_compute_service_profile()
        for profile in node_service_profiles:
            if profile == compute_profile:
                return True
        return False

    def _is_host_storage(self, host):
        hostsconf = self.confman.get_hosts_config_handler()
        node_service_profiles = hostsconf.get_service_profiles(host)
        storage_profile = profiles.Profiles.get_storage_service_profile()
        for profile in node_service_profiles:
            if profile == storage_profile:
                return True
        return False

    def _get_network(self, name, host):
        for network in self.networks:
            if network.name == name:
                return network

        hostsconf = self.confman.get_hosts_config_handler()
        domain = hostsconf.get_host_network_domain(host)
        networkingconf = self.confman.get_networking_config_handler()
        network = Network()
        network.name = name
        network.cidr = networkingconf.get_network_cidr(name, domain)
        for dom in networkingconf.get_network_domains(name):
            network.cidrs.add(networkingconf.get_network_cidr(name, dom))
        network.vlan = None
        try:
            network.vlan = networkingconf.get_network_vlan_id(name, domain)
        except configerror.ConfigError:
            pass

        network.gateway = None
        try:
            network.gateway = networkingconf.get_network_gateway(name, domain)
        except configerror.ConfigError:
            pass

        self.networks.append(network)
        return network

    def _get_platform_cpus(self, host):
        hostsconf = self.confman.get_hosts_config_handler()
        cpus = 0
        try:
            perfprofconf = self.confman.get_performance_profiles_config_handler()
            pprofile = hostsconf.get_performance_profiles(host.name)[0]
            platform_cpus = perfprofconf.get_platform_cpus(pprofile)
            if platform_cpus:
                for alloc in platform_cpus.values():
                    cpus = cpus + int(alloc)
        except configerror.ConfigError:
            pass
        except IndexError:
            pass
        except KeyError:
            pass
        return cpus

    def _get_host(self, name):
        for host in self.hosts:
            if host.name == name:
                return host


        hostsconf = self.confman.get_hosts_config_handler()
        networkprofilesconf = self.confman.get_network_profiles_config_handler()
        networkingconf = self.confman.get_networking_config_handler()

        host = Host()
        host.name = name
        host.is_controller = self._is_host_controller(name)
        host.is_caas_master = self._is_host_caas_master(name)
        host.is_compute = self._is_host_compute(name)
        host.is_storage = self._is_host_storage(name)
        host.is_management = self._is_host_management(name)
        host.hwmgmt_address = hostsconf.get_hwmgmt_ip(name)
        host.hwmgmt_user = hostsconf.get_hwmgmt_user(name)
        host.hwmgmt_password = hostsconf.get_hwmgmt_password(name)
        host.hwmgmt_priv_level = hostsconf.get_hwmgmt_priv_level(name)
        host.mgmt_mac = hostsconf.get_mgmt_mac(name)


        platform_cpus = self._get_platform_cpus(host)
        if platform_cpus:
            host.os_max_threads = platform_cpus
            host.is_performance = True

        hostnetprofiles = hostsconf.get_network_profiles(name)

        hostnetnames = hostsconf.get_host_networks(name)
        domain = hostsconf.get_host_network_domain(name)

        for net in hostnetnames:
            hostnetwork = HostNetwork()
            hostnetwork.network = self._get_network(net, name)
            hostnetwork.interface = hostsconf.get_host_network_interface(name, net)
            hostnetwork.ip_holding_interface = hostsconf.get_host_network_ip_holding_interface(name, net)
            hostnetwork.ip = networkingconf.get_host_ip(name, net)
            mask = networkingconf.get_network_mask(net, domain)
            hostnetwork.ip = hostnetwork.ip + '/' + str(mask)

            hostnetwork.is_bonding = False

            for profile in hostnetprofiles:
                try:
                    bondinginterfaces = networkprofilesconf.get_profile_bonding_interfaces(profile)
                    if hostnetwork.interface in bondinginterfaces:
                        hostnetwork.is_bonding = True
                        hostnetwork.members = networkprofilesconf.get_profile_bonded_interfaces(profile, hostnetwork.interface)
                        hostnetwork.linux_bonding_options = networkprofilesconf.get_profile_linux_bonding_options(profile)
                        break
                except configerror.ConfigError:
                    pass
            host.networks.append(hostnetwork)

        self.hosts.append(host)
        if host.is_controller:
            self.controllers.append(host)
            self.neutron_agent_hosts.add(host)
        if host.is_caas_master:
            self.caas_masters.append(host)
        if host.is_management:
            self.managements.append(host)
        if host.is_compute:
            self.computes.append(host)
            self.neutron_agent_hosts.add(host)
        if host.is_storage:
            self.storages.append(host)


    def _init_jinja_environment(self):
        # initialize networks and hosts
        networkingconf = self.confman.get_networking_config_handler()
        networks = networkingconf.get_networks()
        hostsconf = self.confman.get_hosts_config_handler()
        hosts = hostsconf.get_enabled_hosts()
        for net in networks:
            for host in hosts:
                self._get_network(net, host)
                self._get_host(host)

        # initialize HAS
        self.has.haproxy.external_vip = networkingconf.get_external_vip()
        self.has.haproxy.internal_vip = networkingconf.get_internal_vip()

        # initialize general
        self.general.dns_servers = networkingconf.get_dns()
        timeconf = self.confman.get_time_config_handler()
        self.general.ntp_servers = timeconf.get_ntp_servers()
        self.general.zone = timeconf.get_zone()
        usersconf = self.confman.get_users_config_handler()
        self.general.admin = usersconf.get_admin_user()
        self.general.password = usersconf.get_admin_user_password()
        caas_conf = self.confman.get_caas_config_handler()
        if caas_conf.get_caas_only():
          self.general.openstack_password = caas_conf.get_admin_password()
        else:
          openstackconfighandler = self.confman.get_openstack_config_handler()
          self.general.openstack_password = openstackconfighandler.get_admin_password()
        self.general.admin_authorized_keys = usersconf.get_admin_user_authorized_keys()
