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

# pylint: disable=missing-docstring,invalid-name,too-few-public-methods,too-many-instance-attributes,too-many-lines
import os
import json
from jinja2 import Environment
from cmframework.apis import cmansibleinventoryconfig
from cmframework.apis import cmerror
from cmdatahandlers.api import configerror
from serviceprofiles import profiles
import hw_detector.hw_detect_lib as hw


import math

NEAREST_POWER_OF_2_PERCENTAGE = 0.25

TARGET_PGS_PER_OSD_NO_INCREASE_EXPECTED = 100
TARGET_PGS_PER_OSD_UP_TO_DOUBLE_SIZE_INCREASE_EXPECTED = 200
TARGET_PGS_PER_OSD_TWO_TO_THREE_TIMES_SIZE_INCREASE_EXPECTED = 300
# Please visit ceph.com/pgcalc for details on previous values

MINIMUM_PG_NUM = 32


class PGNum(object):
    """Calculates the pg_num for the given attributes."""

    def __init__(self, number_of_pool_osds, pool_data_percentage, number_of_replicas):
        self._number_of_pool_osds = number_of_pool_osds
        self._pool_data_percentage = pool_data_percentage
        self._number_of_replicas = number_of_replicas

    @staticmethod
    def _round_up_to_closest_power_of_2(num):
        """Smallest power of 2 greater than or equal to num."""
        return 2**(num-1).bit_length() if num > 0 else 1

    @staticmethod
    def _round_down_to_closest_power_of_2(num):
        """Largest power of 2 less than or equal to num."""
        return 2**(num.bit_length()-1) if num > 0 else 1

    @staticmethod
    def _check_percentage_of_values(diff_to_lower, org_pgnum):
        """ If the nearest power of 2 is more than 25% below the original value,
        the next higher power of 2 is used. Please visit ceph.com/pgcalc
        """
        return float(float(diff_to_lower) / float(org_pgnum)) > NEAREST_POWER_OF_2_PERCENTAGE

    def _rounded_pgnum_to_the_nearest_power_of_2(self, pgnum):
        higher_power = self._round_up_to_closest_power_of_2(pgnum)
        lower_power = self._round_down_to_closest_power_of_2(pgnum)
        diff_to_lower = pgnum - lower_power
        if pgnum != 0 and self._check_percentage_of_values(diff_to_lower, pgnum):
            return higher_power
        return lower_power

    def _calculate_pg_num_formula(self, number_of_pool_osds, pool_percentage):
        return TARGET_PGS_PER_OSD_UP_TO_DOUBLE_SIZE_INCREASE_EXPECTED \
               * number_of_pool_osds * float(pool_percentage) / self._number_of_replicas

    def _select_pgnum_formula_result(self, number_of_pool_osds, pool_percentage):
        pgnum = self._calculate_pg_num_formula(number_of_pool_osds, pool_percentage)
        return int(math.ceil(max(pgnum, MINIMUM_PG_NUM)))

    def calculate(self):
        """ The formula of the calculation can be found from ceph.com/pgcalc.

            pgnum = (target_pgs x number_of_osds_in_pool x pool_percentage)/number_of_replicas
            return : rounded pgnum to the nearest power of 2

        """
        pgnum = self._select_pgnum_formula_result(
            self._number_of_pool_osds, self._pool_data_percentage)
        return self._rounded_pgnum_to_the_nearest_power_of_2(pgnum)


NUMBER_OF_POOLS = 4
SUPPORTED_INSTANCE_BACKENDS = ['default', 'cow', 'lvm']
ALL_DEFAULT_INSTANCE_BACKENDS = SUPPORTED_INSTANCE_BACKENDS + ['rbd']

DEFAULT_INSTANCE_LV_PERCENTAGE = "100"

USER_SECRETS = "/etc/openstack_deploy/user_secrets.yml"

# Ceph PG share percentages for Openstack pools
OSD_POOL_IMAGES_PG_NUM_PERCENTAGE = 0.09
OSD_POOL_VOLUMES_PG_NUM_PERCENTAGE = 0.69
OSD_POOL_VMS_PG_NUM_PERCENTAGE = 0.20
OSD_POOL_SHARED_PG_NUM_PERCENTAGE = 0.02
# Ceph PG share percentages for CaaS pools
OSD_POOL_CAAS_PG_NUM_PERCENTAGE = 1.0

DEFAULT_ROOTDISK_DEVICE = "/dev/sda"
# root disk partition 2 system volume group VG percentages
INSTANCE_NODE_VG_PERCENTAGE = 0.47
NOT_INSTANCE_NODE_VG_PERCENTAGE = 1
"""
/dev/sda1 fixed partition size : 50GiB fixed size = 10% of the total disk size
/dev/sda2 system VG partition size: 47% of remaining total disk size = 42% of total disk size
/dev/sda3 instance partition size 53% of remaining total disk size = 47% of total disk size
"""


JSON_EXTERNAL_CEPH_CINDER_BACKEND_HOST_VAR = """
{
    {% for host in hosts %}
    "{{ host.name }}": {
        "ext_ceph_user": "{{ ext_ceph_user }}",
        "ext_ceph_user_key": "{{ ext_ceph_user_key }}",
        "cephkeys_access_group": "cephkeys",

        "ceph_mons": [
            {% for host in hosts %}
                "{{ host.name }}"
                {% if not loop.last %},{% endif %}
            {% endfor %}],

        "ext_ceph_fsid": "{{ ext_ceph_fsid }}",
        "ext_ceph_mon_hosts": "{{ ext_ceph_mon_hosts }}",

        "cinder_service_hostname": "{{ host.name }}",
        "cinder_backends": {
            "rbd": {
                "volume_driver": "cinder.volume.drivers.rbd.RBDDriver",
                "rbd_pool": "{{ cinder_pool_name }}",
                "rbd_ceph_conf": "/etc/ceph/ceph.conf",
                "ceph_conf": "/etc/ceph/ceph.conf",
                "rbd_flatten_volume_from_snapshot": "false",
                "rbd_max_clone_depth": "5",
                "rbd_store_chunk_size": "4",
                "rados_connect_timeout": "-1",
                "volume_backend_name": "RBD",
                "rbd_secret_uuid": "{{ cinder_ceph_client_uuid }}",
                "rbd_user": "{{ ext_ceph_user }}",
                "backend_host": "controller",
                "rbd_exclusive_cinder_pool": "True"
            }
        },

        "ext_openstack_pools": [
            "{{ glance_pool_name }}",
            "{{ cinder_pool_name }}",
            "{{ nova_pool_name }}",
            "{{ platform_pool_name }}"
        ],

        "cinder_ceph_client": "{{ ext_ceph_user }}",
        "nova_ceph_client": "{{ ext_ceph_user }}",

        "glance_default_store": "rbd",
        "glance_additional_stores": ["http", "cinder", "file"],
        "glance_rbd_store_pool": "{{ glance_pool_name }}",
        "glance_rbd_store_chunk_size": "8",
        "glance_ceph_client": "{{ ext_ceph_user }}",
        "ceph_conf": "/etc/ceph/ceph.conf"

    } {% if not loop.last %},{% endif %}
    {% endfor %}
}
"""

JSON_CINDER_BACKENDS_HOST_VAR = """
{
    {%- set loopvar = {'first_entry': True} %}
    {% for host in hosts %}
    {% if host.is_controller %}
    {%- if not loopvar.first_entry %},{%- endif %}
    {%- if loopvar.update({'first_entry': False}) %}{%- endif %}
    "{{ host.name }}": {
        "cinder_service_hostname": "{{ host.name }}",
        "cinder_backends": {
            {% if openstack_storage == 'ceph' %}
            "rbd": {
                "volume_driver": "cinder.volume.drivers.rbd.RBDDriver",
                "rbd_pool": "{{ cinder_pool_name }}",
                "rbd_ceph_conf": "/etc/ceph/ceph.conf",
                "ceph_conf": "/etc/ceph/ceph.conf",
                "rbd_flatten_volume_from_snapshot": "false",
                "rbd_max_clone_depth": "5",
                "rbd_store_chunk_size": "4",
                "rados_connect_timeout": "-1",
                "volume_backend_name": "volumes_hdd",
                "rbd_secret_uuid": "{{ cinder_ceph_client_uuid }}",
                "rbd_user": "cinder",
                "backend_host": "controller",
                "rbd_exclusive_cinder_pool": "True"
            }
            {% endif %}
            {% if openstack_storage == 'lvm' %}
            "lvm": {
                "iscsi_ip_address": "{{ installation_controller_ip }}",
                "volume_backend_name": "LVM_iSCSI",
                "volume_driver": "cinder.volume.drivers.lvm.LVMVolumeDriver",
                "volume_group": "cinder-volumes"
            }
            {% endif %}
        }
    }
    {% endif %}
    {% endfor %}
}
"""

JSON_STORAGE_HOST_VAR = """
{
    {%- set loopvar = {'first_entry': True} %}
    {% for host in hosts %}
    {% if host.is_rbd_ceph %}
    {%- if not loopvar.first_entry %},{%- endif %}
    {%- if loopvar.update({'first_entry': False}) %}{%- endif %}
    "{{ host.name }}": {
         "devices": [
             {% for disk in host.ceph_osd_disks %}
                 "{{disk}}"
                 {%if not loop.last %},{% endif %}{% endfor %}]
    }
    {% endif %}
    {% endfor %}
}
"""

JSON_STORAGE_HOST_DISK_CONFIGURATION = """
{
    {% for host in hosts %}
    "{{ host.name }}": {
         "by_path_disks":
             { "os" : "{{ host.os_disk }}",
               "osd" : "{{ host.ceph_osd_disks }}",
               "osd_disks_ids" : "{{ host.osd_disks_ids }}"
             },
         "rootdisk_vg_percentage": "{{ host.vg_percentage }}",
         "default_rootdisk_device": "{{ rootdisk_device }}"
    } {% if not loop.last %},{% endif %}
    {% endfor %}
}
"""


JSON_LVM_STORAGE_HOST_VAR = """
{
    {% for host in hosts %}
    "{{ host.name }}": {
         "devices": [
             {% for disk in host.cinder_disks %}
             "{{disk}}"
             {%if not loop.last %},{% endif %}{% endfor %}],
         "cinder_physical_volumes": [
             {% for disk in host.cinder_physical_volumes %}
             "{{disk}}"
             {%if not loop.last %},{% endif %}{% endfor %}]
    } {% if not loop.last %},{% endif %}
    {% endfor %}
}
"""


JSON_BARE_LVM_STORAGE_HOST_VAR = """
{
    {% for host in hosts %}
    "{{ host.name }}": {
        {% if host.is_bare_lvm %}
        "bare_lvm": {
            "disks": [
                {% for disk in host.bare_lvm_disks %}
                    "{{disk}}"
                    {%if not loop.last %},{% endif %}{% endfor %}],
            "physical_volumes": [
                {% for disk in host.bare_lvm_physical_volumes %}
                    "{{disk}}"
                    {%if not loop.last %},{% endif %}{% endfor %}],
            "mount_options": "{{ host.mount_options }}",
            "mount_dir": "{{ host.mount_dir }}",
            "name": "{{ host.bare_lvm_lv_name }}"
        }
        {% endif %}
    } {% if not loop.last %},{% endif %}
    {% endfor %}
}
"""

JSON_DEVICE_HOST_VAR = """
{
    {%- set loopvar = {'first_entry': True} %}
    {% for host in hosts %}
    {% if host.instance_physical_volumes %}
    {%- if not loopvar.first_entry %},{%- endif %}
    {%- if loopvar.update({'first_entry': False}) %}{%- endif %}
    "{{ host.name }}": {
         "instance_disks": [
             {% for disk in host.instance_disks %}
                 "{{disk}}"
                 {%if not loop.last %},{% endif %}
             {% endfor %}],
         "instance_physical_volumes": [
             {% for disk in host.instance_physical_volumes %}
                 "{{disk}}"
                 {%if not loop.last %},{% endif %}
             {% endfor %}],
         "instance_lv_percentage": "{{ host.instance_lv_percentage }}"
    }
    {% endif %}
    {% endfor %}
}
"""

# /etc/ansible/roles/os_nova/templates/nova.conf.j2
JSON_NOVA_RBD_HOST_VAR = """
{
    {% for host in hosts %}
    "{{ host.name }}": {
         "nova_libvirt_images_rbd_pool": "{{ nova_pool_name }}",
         "nova_ceph_client": "{{ nova_ceph_client }}"
    } {% if not loop.last %},{% endif %}
    {% endfor %}
}
"""


#
# /opt/ceph-ansible/group_vars/osds.yml
JSON_OVERRIDE = """
{
    "ceph_conf_overrides": {
        "global": {
            "mon_max_pg_per_osd": "400",
            "mon_pg_warn_max_object_skew": "-1",
            "osd_pool_default_size": "{{ osd_pool_default_size }}",
            "osd_pool_default_min_size": "{{ osd_pool_default_min_size }}",
            "osd_pool_default_pg_num": "{{ osd_pool_default_pg_num }}",
            "osd_pool_default_pgp_num": "{{ osd_pool_default_pg_num }}",
            "osd_heartbeat_grace": "3",
            "osd_heartbeat_interval": "2",
            "mon_osd_min_down_reporters": "1",
            "mon_osd_adjust_heartbeat_grace": "false",
            "auth_client_required": "cephx"
        },
        "mgr": {
            "mgr_modules": "dashboard"
        },
        "mon": {
            "mon_health_preluminous_compat_warning": "false",
            "mon_health_preluminous_compat": "true",
            "mon_timecheck_interval": "60",
            "mon_sd_reporter_subtree_level": "device",
            "mon_clock_drift_allowed": "0.1"
        },
        "osd": {
            "osd_mon_heartbeat_interval": "10",
            "osd_mon_report_interval_min": "1",
            "osd_mon_report_interval_max": "15"
        }
    }
}
"""
JSON_OVERRIDE_CACHE = """
{
    "ceph_conf_overrides": {
        "global": {
            "mon_max_pg_per_osd": "400",
            "mon_pg_warn_max_object_skew": "-1",
            "osd_pool_default_size": "{{ osd_pool_default_size }}",
            "osd_pool_default_min_size": "{{ osd_pool_default_min_size }}",
            "osd_pool_default_pg_num": "{{ osd_pool_default_pg_num }}",
            "osd_pool_default_pgp_num": "{{ osd_pool_default_pg_num }}",
            "osd_heartbeat_grace": "3",
            "osd_heartbeat_interval": "2",
            "mon_osd_adjust_heartbeat_grace": "false",
            "bluestore_cache_size": "1073741824",
            "auth_client_required": "cephx"
        },
        "mgr": {
            "mgr_modules": "dashboard"
        },
        "mon": {
            "mon_health_preluminous_compat_warning": "false",
            "mon_health_preluminous_compat": "true",
            "mon_timecheck_interval": "60",
            "mon_sd_reporter_subtree_level": "device",
            "mon_clock_drift_allowed": "0.1"
        },
        "osd": {
            "osd_mon_heartbeat_interval": "10",
            "osd_mon_report_interval_min": "1",
            "osd_mon_report_interval_max": "15"
        }
    }
}
"""
JSON_OVERRIDE_3CONTROLLERS = """
{
    "ceph_conf_overrides": {
        "global": {
            "mon_max_pg_per_osd": "400",
            "mon_pg_warn_max_object_skew": "-1",
            "osd_pool_default_size": "{{ osd_pool_default_size }}",
            "osd_pool_default_min_size": "{{ osd_pool_default_min_size }}",
            "osd_pool_default_pg_num": "{{ osd_pool_default_pg_num }}",
            "osd_pool_default_pgp_num": "{{ osd_pool_default_pg_num }}",
            "osd_heartbeat_grace": "3",
            "osd_heartbeat_interval": "2",
            "mon_osd_adjust_heartbeat_grace": "false",
            "bluestore_cache_size": "1073741824",
            "auth_client_required": "cephx"
        },
        "mgr": {
            "mgr_modules": "dashboard"
        },
        "mon": {
            "mon_health_preluminous_compat_warning": "false",
            "mon_health_preluminous_compat": "true",
            "mon_lease": "1.0",
            "mon_election_timeout": "2",
            "mon_lease_renew_interval_factor": "0.4",
            "mon_lease_ack_timeout_factor": "1.5",
            "mon_timecheck_interval": "60",
            "mon_sd_reporter_subtree_level": "device",
            "mon_clock_drift_allowed": "0.1"
        },
        "osd": {
            "osd_mon_heartbeat_interval": "10",
            "osd_mon_report_interval_min": "1",
            "osd_mon_report_interval_max": "15"
        }
    }
}
"""

JSON_NETWORK = """
{
    "public_network": "{{ public_networks }}",
    "cluster_network": "{{ cluster_networks }}"
}
"""

JSON_OS_TUNING = """
{
    "os_tuning_params": [{
        "name": "vm.min_free_kbytes",
        "value": "1048576"
    }]
}
"""

JSON_OSD_POOL_PGNUMS = """
{
    "osd_pool_images_pg_num": "{{ osd_pool_images_pg_num }}",
    "osd_pool_volumes_pg_num": "{{ osd_pool_volumes_pg_num }}",
    "osd_pool_vms_pg_num": "{{ osd_pool_vms_pg_num }}",
    "osd_pool_shared_pg_num": "{{ osd_pool_shared_pg_num }}"{%- if 0 < osd_pool_caas_pg_num %},
    "osd_pool_caas_pg_num": "{{ osd_pool_caas_pg_num }}"
{% endif %}
}
"""

JSON_CEPH_HOSTS = """
{
    "ceph-mon": [ {% for host in mons %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ],
    "ceph-mon_hosts": [ {% for host in mons %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ],
    "mons": [ {% for host in mons %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ],
    "ceph_mons": [ {% for host in mons %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ],
    "ceph-osd": [ {% for host in osds %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ],
    "ceph-osd_hosts": [ {% for host in osds %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ],
    "osds": [ {% for host in osds %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ],
    "mgrs": [ {% for host in mgrs %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ],
    "ceph-mgr": [ {% for host in mgrs %}"{{ host.name }}"{% if not loop.last %},{% endif %}{% endfor %} ]
}
"""
#    "storage_backend": ceph


# Replaces variables in /opt/openstack-ansible/playbooks/inventory/group_vars/glance_all.yml
JSON_GLANCE_CEPH_ALL_GROUP_VARS = """
{
    {% for host in hosts %}
    "{{ host.name }}": {
        "glance_default_store": "rbd",
        "glance_additional_stores": ["http", "cinder", "file"],
        "glance_rbd_store_pool": "{{ glance_pool_name }}",
        "glance_rbd_store_chunk_size": "8",
        "ceph_conf": "/etc/ceph/ceph.conf"
    } {% if not loop.last %},{% endif %}
    {% endfor %}
}
"""

JSON_GLANCE_LVM_ALL_GROUP_VARS = """
{
    {% for host in hosts %}
    "{{ host.name }}": {
        "glance_default_store": "file"
    } {% if not loop.last %},{% endif %}
    {% endfor %}
}
"""

# ceph-ansible variables must be set at host_vars -level
# ceph-ansible sample variables in group_vars
# group_vars - all.yml.sample
JSON_CEPH_ANSIBLE_ALL_HOST_VARS = """
{
    {% for host in hosts %}
    "{{ host.name }}": {
         "mon_group_name": "mons",
         "osd_group_name": "osds",
         "mgr_group_name": "mgrs",
         "ceph_stable_release": "luminous",
         "generate_fsid": "true",
         "cephx": "true",
         "journal_size": "10240",
         "osd_objectstore": "bluestore"
    } {% if not loop.last %},{% endif %}
    {% endfor %}
}
"""

# pylint: disable=line-too-long
# ceph-ansible
# group_vars - mons.yml.sample
JSON_CEPH_ANSIBLE_MONS_HOST_VARS = """
{
    {% for host in hosts %}
    "{{ host.name }}": {
         "monitor_secret": "{{ '{{ monitor_keyring.stdout }}' }}",
         "openstack_config": true,
         "cephkeys_access_group": "cephkeys",
         "openstack_pools": [
             {
                 "name": "{{ platform_pool }}",
                 "pg_num": "{{ osd_pool_shared_pg_num }}",
                 "rule_name": ""
             }{% if is_openstack_deployment %},
             {
                 "name": "{{ glance_pool }}",
                 "pg_num": "{{ osd_pool_images_pg_num }}",
                 "rule_name": ""
             },
             {
                 "name": "{{ cinder_pool }}",
                 "pg_num": "{{ osd_pool_volumes_pg_num }}",
                 "rule_name": ""
             },
             {
                 "name": "{{ nova_pool }}",
                 "pg_num": "{{ osd_pool_vms_pg_num }}",
                 "rule_name": ""
             }
        {%- endif %}
        {%- if is_caas_deployment and 0 < osd_pool_caas_pg_num %},
             {
                 "name": "caas",
                 "pg_num": "{{ osd_pool_caas_pg_num }}",
                 "rule_name": ""
             }
        {%- endif %}
         ],
         "openstack_keys": [
             {
                 "acls": [],
                 "key": "$(ceph-authtool --gen-print-key)",
                 "mode": "0600",
                 "mon_cap": "allow r",
                 "name": "client.shared",
                 "osd_cap": "allow class-read object_prefix rbd_children, allow rwx pool={{ platform_pool }}"
             }{% if is_openstack_deployment %},
             {
                 "acls": [],
                 "key": "$(ceph-authtool --gen-print-key)",
                 "mode": "0640",
                 "mon_cap": "allow r",
                 "name": "client.glance",
                 "osd_cap": "allow class-read object_prefix rbd_children, allow rwx pool={{ glance_pool }}"
             },
             {
                 "acls": [],
                 "key": "$(ceph-authtool --gen-print-key)",
                 "mode": "0640",
                 "mon_cap": "allow r, allow command \\\\\\\\\\\\\\"osd blacklist\\\\\\\\\\\\\\"",
                 "name": "client.cinder",
                 "osd_cap": "allow class-read object_prefix rbd_children, allow rwx pool={{ cinder_pool }}, allow rwx pool={{ nova_pool }}, allow rx pool={{ glance_pool }}"
             }
        {%- endif %}
        {%- if is_caas_deployment and 0 < osd_pool_caas_pg_num %},
             {
                 "acls": [],
                 "key": "$(ceph-authtool --gen-print-key)",
                 "mode": "0600",
                 "mon_cap": "allow r",
                 "name": "client.caas",
                 "osd_cap": "allow class-read object_prefix rbd_children, allow rwx pool=caas"
             }
        {%- endif %}
        ]
    } {% if not loop.last %},{% endif %}
    {% endfor %}
}
"""
# pylint: enable=line-too-long

# ceph-ansible
# group_vars - osds.yml.sample
JSON_CEPH_ANSIBLE_OSDS_HOST_VARS = """
{
    {% for host in hosts %}
    "{{ host.name }}": {
         "raw_journal_devices": [],
         "journal_collocation": true,
         "raw_multi_journal": false,
         "dmcrytpt_journal_collocation": false,
         "dmcrypt_dedicated_journal": false,
         "osd_scenario": "collocated",
         "dedicated_devices": []
    } {% if not loop.last %},{% endif %}
    {% endfor %}
}
"""


JSON_SINGLE_CONTROLLER_VAR = """
{
    {% for host in hosts %}
    "{{ host.name }}": {
         "single_controller_host": true
    } {% if not loop.last %},{% endif %}
    {% endfor %}
}
"""


class Host(object):
    def __init__(self):
        self.name = None
        self.is_lvm = None
        self.is_osd = None
        self.is_mon = None
        self.is_mgr = None
        self.is_rbd_ceph = None
        self.ceph_osd_disks = []
        self.lvm_disks = []
        self.cinder_disks = []
        self.is_controller = False
        self.is_compute = False
        self.is_storage = False
        self.instance_physical_volumes = []
        self.cinder_physical_volumes = []
        self.instance_disks = []
        self.instance_lv_percentage = ""
        self.os_disk = ""
        self.osd_disks_ids = []
        self.vg_percentage = NOT_INSTANCE_NODE_VG_PERCENTAGE
        self.mount_dir = ""
        self.bare_lvm_disks = None
        self.is_bare_lvm = None
        self.bare_lvm_physical_volumes = None
        self.mount_options = None
        self.bare_lvm_lv_name = None


class storageinventory(cmansibleinventoryconfig.CMAnsibleInventoryConfigPlugin):

    def __init__(self, confman, inventory, ownhost):
        super(storageinventory, self).__init__(confman, inventory, ownhost)
        self.hosts = []
        self.storage_hosts = []
        self.compute_hosts = []
        self.controller_hosts = []
        self._mon_hosts = []
        self._osd_hosts = []
        self._mgr_hosts = []
        self.single_node_config = False
        self._networking_config_handler = self.confman.get_networking_config_handler()
        self._hosts_config_handler = self.confman.get_hosts_config_handler()
        self._storage_config_handler = self.confman.get_storage_config_handler()
        self._openstack_config_handler = self.confman.get_openstack_config_handler()
        self._sp_config_handler = self.confman.get_storage_profiles_config_handler()
        self._caas_config_handler = self.confman.get_caas_config_handler()
        self._ceph_caas_pg_proportion = 0.0
        self._ceph_openstack_pg_proportion = 0.0
        self._cinder_pool_name = 'volumes'
        self._glance_pool_name = 'images'
        self._nova_pool_name = 'vms'
        self._platform_pool_name = 'shared'
        self._storage_profile_attribute_properties = {
            'lvm_cinder_storage_partitions': {
                'backends': ['lvm'],
                'getter': self._sp_config_handler.get_profile_lvm_cinder_storage_partitions
            },
            'mount_options': {
                'backends': ['bare_lvm'],
                'getter': self._sp_config_handler.get_profile_bare_lvm_mount_options
            },
            'mount_dir': {
                'backends': ['bare_lvm'],
                'getter': self._sp_config_handler.get_profile_bare_lvm_mount_dir
            },
            'lv_name': {
                'backends': ['bare_lvm'],
                'getter': self._sp_config_handler.get_profile_bare_lvm_lv_name
            },
            'nr_of_ceph_osd_disks': {
                'backends': ['ceph'],
                'getter': self._sp_config_handler.get_profile_nr_of_ceph_osd_disks
            },
            'lvm_instance_storage_partitions': {
                'backends': ['lvm', 'bare_lvm'],
                'getter': self._sp_config_handler.get_profile_lvm_instance_storage_partitions
            },
            'lvm_instance_cow_lv_storage_percentage': {
                'backends': ['lvm'],
                'getter': self._sp_config_handler.get_profile_lvm_instance_cow_lv_storage_percentage
            },
            'openstack_pg_proportion': {
                'backends': ['ceph'],
                'getter': self._sp_config_handler.get_profile_ceph_openstack_pg_proportion
            },
            'caas_pg_proportion': {
                'backends': ['ceph'],
                'getter': self._sp_config_handler.get_profile_ceph_caas_pg_proportion
            },
        }

    def _is_host_managment(self, host):
        return self._is_profile_in_hosts_profiles(profiles.Profiles.get_management_service_profile(), host)

    def _is_host_controller(self, host):
        return self._is_profile_in_hosts_profiles(profiles.Profiles.get_controller_service_profile(), host)

    def _is_profile_in_hosts_profiles(self, profile, host):
        node_service_profiles = self._hosts_config_handler.get_service_profiles(host)
        return profile in node_service_profiles

    def _is_host_compute(self, host):
        return self._is_profile_in_hosts_profiles(profiles.Profiles.get_compute_service_profile(), host)

    def _is_host_caas_master(self, host):
        return self._is_profile_in_hosts_profiles(profiles.Profiles.get_caasmaster_service_profile(), host)

    def _is_host_storage(self, host):
        return self._is_profile_in_hosts_profiles(profiles.Profiles.get_storage_service_profile(), host)

    def _is_controller_has_compute(self):
        if set.intersection(set(self.compute_hosts), set(self.controller_hosts)):
            return True
        return False

    def _is_collocated_controller_node_config(self):
        if set.intersection(set(self.storage_hosts), set(self.controller_hosts)):
            return True
        return False

    def _is_collocated_3controllers_config(self):
        if (self._is_collocated_controller_node_config() and
                (len(self.controller_hosts) == 3) and (len(self.hosts) == 3)):
            return True
        return False

    def _is_dedicated_storage_config(self):
        collocated_config = set.intersection(set(self.storage_hosts), set(self.controller_hosts))
        if collocated_config and (collocated_config == set(self.controller_hosts)):
            return False
        elif self.storage_hosts:
            return True
        else:
            return False

    def handle_bootstrapping(self):
        self.handle('bootstrapping')

    def handle_provisioning(self):
        self.handle('provisioning')

    def handle_postconfig(self):
        self.handle('postconfig')

    def handle_setup(self):
        pass

    def _template_and_add_vars_to_hosts(self, template, **variables):
        try:
            text = Environment().from_string(template).render(variables)
            if text:
                self._add_vars_for_hosts(text)
        except Exception as exp:
            raise cmerror.CMError(str(exp))

    def _add_vars_for_hosts(self, inventory_text):
        inventory = json.loads(inventory_text)
        for host in inventory.keys():
            for var, value in inventory[host].iteritems():
                self.add_host_var(host, var, value)

    @staticmethod
    def _read_cinder_ceph_client_uuid():
        if os.path.isfile(USER_SECRETS):
            d = dict(line.split(':', 1) for line in open(USER_SECRETS))
            cinder_ceph_client_uuid = d['cinder_ceph_client_uuid'].strip()
            return cinder_ceph_client_uuid
        else:
            raise cmerror.CMError("The file {} does not exist.".format(USER_SECRETS))

    def _add_cinder_backends(self):
        self._template_and_add_vars_to_hosts(
            JSON_CINDER_BACKENDS_HOST_VAR,
            hosts=self.controller_hosts,
            installation_controller_ip=self._installation_host_ip,
            cinder_ceph_client_uuid=self._read_cinder_ceph_client_uuid(),
            openstack_storage=self._openstack_config_handler.get_storage_backend(),
            cinder_pool_name=self._cinder_pool_name)

    def _add_external_ceph_cinder_backends(self):
        handler = self._storage_config_handler
        self._template_and_add_vars_to_hosts(
            JSON_EXTERNAL_CEPH_CINDER_BACKEND_HOST_VAR,
            hosts=self.hosts,
            cinder_ceph_client_uuid=self._read_cinder_ceph_client_uuid(),
            ext_ceph_user=handler.get_ext_ceph_ceph_user(),
            ext_ceph_user_key=handler.get_ext_ceph_ceph_user_key(),
            ext_ceph_fsid=handler.get_ext_ceph_fsid(),
            ext_ceph_mon_hosts=", ".join(handler.get_ext_ceph_mon_hosts()),
            nova_pool_name=self._nova_pool_name,
            glance_pool_name=self._glance_pool_name,
            cinder_pool_name=self._cinder_pool_name,
            platform_pool_name=self._platform_pool_name)

    def _add_storage_nodes_configs(self):
        rbdhosts = []
        for host in self.hosts:
            if host.is_rbd_ceph:
                rbdhosts.append(host)
        self._template_and_add_vars_to_hosts(JSON_STORAGE_HOST_VAR, hosts=rbdhosts)

    def _add_hdd_storage_configs(self):
        self._template_and_add_vars_to_hosts(
            JSON_STORAGE_HOST_DISK_CONFIGURATION,
            hosts=self.hosts,
            rootdisk_device=DEFAULT_ROOTDISK_DEVICE)

    def _add_lvm_storage_configs(self):
        self._template_and_add_vars_to_hosts(JSON_LVM_STORAGE_HOST_VAR, hosts=self.hosts)

    def _add_bare_lvm_storage_configs(self):
        self._template_and_add_vars_to_hosts(JSON_BARE_LVM_STORAGE_HOST_VAR, hosts=self.hosts)

    def _add_instance_devices(self):
        self._template_and_add_vars_to_hosts(JSON_DEVICE_HOST_VAR, hosts=self.compute_hosts)

    def _add_ceph_hosts(self):
        self._add_host_group(
            Environment().from_string(JSON_CEPH_HOSTS).render(
                mons=self._mon_hosts,
                osds=self._osd_hosts,
                mgrs=self._mgr_hosts))

        self._add_global_parameters(
            Environment().from_string(JSON_CEPH_HOSTS).render(
                mons=self._mon_hosts,
                osds=self._osd_hosts,
                mgrs=self._mgr_hosts))

    def _add_glance(self):
        if self.is_ceph_backend:
            self._template_and_add_vars_to_hosts(
                JSON_GLANCE_CEPH_ALL_GROUP_VARS,
                hosts=self.hosts,
                glance_pool_name=self._glance_pool_name)
        elif self.is_lvm_backend:
            self._template_and_add_vars_to_hosts(JSON_GLANCE_LVM_ALL_GROUP_VARS, hosts=self.hosts)

    def _add_ceph_ansible_all_sample_host_vars(self):
        self._template_and_add_vars_to_hosts(JSON_CEPH_ANSIBLE_ALL_HOST_VARS, hosts=self.hosts)

    def _add_ceph_ansible_mons_sample_host_vars(self):
        self._template_and_add_vars_to_hosts(
            JSON_CEPH_ANSIBLE_MONS_HOST_VARS,
            hosts=self.hosts,
            **self._get_ceph_vars())

    def _get_ceph_vars(self):
        return {
            'osd_pool_images_pg_num':  self._calculated_images_pg_num,
            'osd_pool_volumes_pg_num': self._calculated_volumes_pg_num,
            'osd_pool_vms_pg_num':     self._calculated_vms_pg_num,
            'osd_pool_shared_pg_num':  self._calculated_shared_pg_num,
            'osd_pool_caas_pg_num':    self._calculated_caas_pg_num,
            'is_openstack_deployment': self._is_openstack_deployment,
            'is_caas_deployment':      self._is_caas_deployment,
            'is_hybrid_deployment':    self._is_hybrid_deployment,
            'nova_pool':               self._nova_pool_name,
            'glance_pool':             self._glance_pool_name,
            'cinder_pool':             self._cinder_pool_name,
            'platform_pool':           self._platform_pool_name
        }

    def _add_ceph_ansible_osds_sample_host_vars(self):
        self._template_and_add_vars_to_hosts(JSON_CEPH_ANSIBLE_OSDS_HOST_VARS, hosts=self.hosts)

    def _add_nova(self):
        if self.is_external_ceph_backend:
            nova_ceph_client = self._storage_config_handler.get_ext_ceph_ceph_user()
        else:
            nova_ceph_client = 'cinder'

        self._template_and_add_vars_to_hosts(
            JSON_NOVA_RBD_HOST_VAR, hosts=self.compute_hosts,
            nova_pool_name=self._nova_pool_name,
            nova_ceph_client=nova_ceph_client)

    def _add_single_controller_host_var(self):
        self._template_and_add_vars_to_hosts(
            JSON_SINGLE_CONTROLLER_VAR, hosts=self.controller_hosts)

    def _add_global_parameters(self, text):
        try:
            inventory = json.loads(text)
            for var, value in inventory.iteritems():
                self.add_global_var(var, value)
        except Exception as exp:
            raise cmerror.CMError(str(exp))

    def _add_host_group(self, text):
        try:
            inventory = json.loads(text)
            for var, value in inventory.iteritems():
                self.add_host_group(var, value)
        except Exception as exp:
            raise cmerror.CMError(str(exp))

    @property
    def cluster_network_cidrs(self):
        cidrs = []
        network = self._networking_config_handler.get_infra_storage_cluster_network_name()
        for domain in self._networking_config_handler.get_network_domains(network):
            cidrs.append(self._networking_config_handler.get_network_cidr(network, domain))
        return ','.join(cidrs)

    @property
    def public_network_cidrs(self):
        cidrs = set()
        cluster_network = self._networking_config_handler.get_infra_storage_cluster_network_name()
        public_network = self._networking_config_handler.get_infra_internal_network_name()
        for domain in self._networking_config_handler.get_network_domains(cluster_network):
            cidrs.add(self._networking_config_handler.get_network_cidr(public_network, domain))
        for host in self._mon_hosts:
            domain = self._hosts_config_handler.get_host_network_domain(host.name)
            cidrs.add(self._networking_config_handler.get_network_cidr(public_network, domain))
        return ','.join(cidrs)

    def _add_networks(self):
        self._add_global_parameters(
            Environment().from_string(JSON_NETWORK).render(
                public_networks=self.public_network_cidrs,
                cluster_networks=self.cluster_network_cidrs))

    def _add_monitor_address(self):
        infra_storage_network = self._networking_config_handler.get_infra_internal_network_name()
        for host in self._mon_hosts:
            monitor_address = \
                self._networking_config_handler.get_host_ip(host.name, infra_storage_network)
            self.add_host_var(host.name, "monitor_address", monitor_address)

    def _add_override_settings(self):
        ceph_osd_pool_size = self._storage_config_handler.get_ceph_osd_pool_size()

        if self._is_collocated_3controllers_config():
            self._add_global_parameters(
                Environment().from_string(JSON_OVERRIDE_3CONTROLLERS).render(
                    osd_pool_default_size=ceph_osd_pool_size,
                    osd_pool_default_min_size=str(ceph_osd_pool_size-1),
                    osd_pool_default_pg_num=self._calculated_default_pg_num))

            self._add_global_parameters(
                Environment().from_string(JSON_OS_TUNING).render())

        elif self._is_controller_has_compute():
            self._add_global_parameters(
                Environment().from_string(JSON_OVERRIDE_CACHE).render(
                    osd_pool_default_size=ceph_osd_pool_size,
                    osd_pool_default_min_size=str(ceph_osd_pool_size-1),
                    osd_pool_default_pg_num=self._calculated_default_pg_num))

            self._add_global_parameters(
                Environment().from_string(JSON_OS_TUNING).render())
        else:
            self._add_global_parameters(
                Environment().from_string(JSON_OVERRIDE).render(
                    osd_pool_default_size=ceph_osd_pool_size,
                    osd_pool_default_min_size=str(ceph_osd_pool_size-1),
                    osd_pool_default_pg_num=self._calculated_default_pg_num))

    def _calculate_pg_num(self, pool_data_percentage):
        pgnum = PGNum(self._total_number_of_osds,
                      pool_data_percentage,
                      self._number_of_replicas)
        return pgnum.calculate()

    @property
    def _calculated_default_pg_num(self):
        return self._calculate_pg_num(self._pool_data_percentage)

    @property
    def _calculated_volumes_pg_num(self):
        return self._calculate_pg_num(
            OSD_POOL_VOLUMES_PG_NUM_PERCENTAGE * self._ceph_openstack_pg_proportion)

    @property
    def _calculated_images_pg_num(self):
        return self._calculate_pg_num(
            OSD_POOL_IMAGES_PG_NUM_PERCENTAGE * self._ceph_openstack_pg_proportion)

    @property
    def _calculated_vms_pg_num(self):
        return self._calculate_pg_num(
            OSD_POOL_VMS_PG_NUM_PERCENTAGE * self._ceph_openstack_pg_proportion)

    @property
    def _calculated_shared_pg_num(self):
        return self._calculate_pg_num(
            OSD_POOL_SHARED_PG_NUM_PERCENTAGE)

    @property
    def _calculated_caas_pg_num(self):
        if self._ceph_caas_pg_proportion > 0:
            return self._calculate_pg_num(
                (OSD_POOL_CAAS_PG_NUM_PERCENTAGE - OSD_POOL_SHARED_PG_NUM_PERCENTAGE) *
                self._ceph_caas_pg_proportion)
        return 0

    def _add_osd_pool_pg_nums(self):
        self._add_global_parameters(
            Environment().from_string(JSON_OSD_POOL_PGNUMS).render(**self._get_ceph_vars()))

    @property
    def _installation_host(self):
        return self._hosts_config_handler.get_installation_host()

    @property
    def _infra_internal_network_name(self):
        return self._networking_config_handler.get_infra_internal_network_name()

    @property
    def _installation_host_ip(self):
        return self._networking_config_handler.get_host_ip(
            self._installation_host, self._infra_internal_network_name)

    @property
    def is_ceph_backend(self):
        return self._storage_config_handler.is_ceph_enabled()

    @property
    def is_external_ceph_backend(self):
        return (self._storage_config_handler.is_external_ceph_enabled() and
                self._ceph_is_openstack_storage_backend)

    def _set_external_ceph_pool_names(self):
        if self.is_external_ceph_backend:
            h = self._storage_config_handler
            self._nova_pool_name = h.get_ext_ceph_nova_pool()
            self._cinder_pool_name = h.get_ext_ceph_cinder_pool()
            self._glance_pool_name = h.get_ext_ceph_glance_pool()
            self._platform_pool_name = h.get_ext_ceph_platform_pool()

    @property
    def _lvm_is_openstack_storage_backend(self):
        return True if self._openstack_config_handler.get_storage_backend() == 'lvm' else False

    @property
    def _ceph_is_openstack_storage_backend(self):
        return True if self._openstack_config_handler.get_storage_backend() == 'ceph' else False

    @property
    def is_lvm_backend(self):
        return (self._storage_config_handler.is_lvm_enabled() and
                self._lvm_is_openstack_storage_backend)

    @property
    def instance_default_backend(self):
        return self._openstack_config_handler.get_instance_default_backend()

    @property
    def _hosts_with_ceph_storage_profile(self):
        # return filter(lambda host: host.is_rbd, self.hosts)
        return [host for host in self.hosts if host.is_rbd_ceph]

    @property
    def _is_openstack_deployment(self):
        return self._caas_config_handler.is_openstack_deployment()

    @property
    def _is_caas_deployment(self):
        return self._caas_config_handler.is_caas_deployment()

    @property
    def _is_hybrid_deployment(self):
        return self._caas_config_handler.is_hybrid_deployment()

    def handle(self, phase):
        self._init_jinja_environment()
        self.add_global_var("external_ceph_configured", self.is_external_ceph_backend)
        self.add_global_var("ceph_configured", self.is_ceph_backend)
        self.add_global_var("lvm_configured", self.is_lvm_backend)
        if phase == 'bootstrapping':
            self._add_hdd_storage_configs()
        else:
            self._add_hdd_storage_configs()
            if self.is_external_ceph_backend:
                self._set_external_ceph_pool_names()
                self._add_external_ceph_cinder_backends()
            else:
                if self._is_openstack_deployment:
                    self._add_cinder_backends()
                    self._add_glance()

            ceph_hosts = self._hosts_with_ceph_storage_profile
            if ceph_hosts:
                self._set_ceph_pg_proportions(ceph_hosts)
                self._add_ceph_ansible_all_sample_host_vars()
                self._add_ceph_ansible_mons_sample_host_vars()
                self._add_ceph_ansible_osds_sample_host_vars()
                self._add_ceph_hosts()
                self._add_storage_nodes_configs()
                self._add_monitor_address()
                self._add_override_settings()
                self._add_osd_pool_pg_nums()
                self._add_networks()
                self.add_global_var("cinder_ceph_client_uuid", self._read_cinder_ceph_client_uuid())
            if self.is_lvm_backend:
                self._add_lvm_storage_configs()
            self._add_bare_lvm_storage_configs()

            self.add_global_var("instance_default_backend", self.instance_default_backend)
            self.add_global_var("storage_single_node_config", self.single_node_config)
            self.add_global_var("one_controller_node_config", self._is_one_controller_node_config)
            if self._is_one_controller_node_config:
                self._add_single_controller_host_var()
            self.add_global_var("collocated_controller_node_config",
                                self._is_collocated_controller_node_config())
            self.add_global_var("dedicated_storage_node_config",
                                self._is_dedicated_storage_config())
            self.add_global_var("storage_one_controller_multi_nodes_config",
                                self._is_one_controller_multi_nodes_config)
            if self.instance_default_backend == 'rbd':
                self._add_nova()
            elif self.instance_default_backend in SUPPORTED_INSTANCE_BACKENDS:
                self._add_instance_devices()

    def _set_ceph_pg_proportions(self, ceph_hosts):
        # FIXME: First storage host's storage profile assumed to get pg proportion values
        hostname = ceph_hosts[0].name
        if self._is_hybrid_deployment:
            self._ceph_openstack_pg_proportion = self._get_ceph_openstack_pg_proportion(hostname)
            self._ceph_caas_pg_proportion = self._get_ceph_caas_pg_proportion(hostname)
        elif self._is_openstack_deployment:
            self._ceph_openstack_pg_proportion = 1.0
            self._ceph_caas_pg_proportion = 0.0
        elif self._is_caas_deployment:
            self._ceph_openstack_pg_proportion = 0.0
            self._ceph_caas_pg_proportion = 1.0

    def _init_host_data(self):
        hosts = self._hosts_config_handler.get_enabled_hosts()
        self.single_node_config = True if len(hosts) == 1 else False
        for name in hosts:
            host = self._initialize_host_object(name)
            self.hosts.append(host)
            if host.is_osd:
                self._osd_hosts.append(host)
            if host.is_mon:
                self._mon_hosts.append(host)
            if host.is_mgr:
                self._mgr_hosts.append(host)

        for host in self.hosts:
            if host.is_compute:
                self.compute_hosts.append(host)
            if host.is_controller:
                self.controller_hosts.append(host)
            if host.is_storage:
                self.storage_hosts.append(host)

    @property
    def _number_of_osd_hosts(self):
        return len(self._osd_hosts)

    @property
    def _is_one_controller_multi_nodes_config(self):
        if len(self.controller_hosts) == 1 and not self.single_node_config:
            return True
        return False

    @property
    def _is_one_controller_node_config(self):
        if len(self.controller_hosts) == 1:
            return True
        return False

    @property
    def _number_of_osds_per_host(self):
        first_osd_host = self._osd_hosts[0].name
        return self._get_nr_of_ceph_osd_disks(first_osd_host)

    @property
    def _total_number_of_osds(self):
        return self._number_of_osds_per_host * self._number_of_osd_hosts

    @property
    def _number_of_pools(self):
        """TODO: Get dynamically"""
        return NUMBER_OF_POOLS

    @property
    def _pool_data_percentage(self):
        return float(1.0 / self._number_of_pools)

    @property
    def _number_of_replicas(self):
        num = self._storage_config_handler.get_ceph_osd_pool_size()
        return 2 if num == 0 else num

    def _init_jinja_environment(self):
        self._init_host_data()

    def _is_backend_configured(self, backend, host_name):
        try:
            if self._get_storage_profile_for_backend(host_name, backend):
                return True
            return False
        except configerror.ConfigError:
            return False

    def _get_storage_profile_for_backend(self, host_name, *backends):
        storage_profiles = self._hosts_config_handler.get_storage_profiles(host_name)
        sp_handler = self._sp_config_handler
        for storage_profile in storage_profiles:
            if sp_handler.get_profile_backend(storage_profile) in backends:
                return storage_profile
        return None

    def _get_nr_of_ceph_osd_disks(self, host_name):
        return self._get_storage_profile_attribute(host_name, 'nr_of_ceph_osd_disks')

    def _get_storage_profile_attribute(self, host_name, attribute):
        attribute_properties = self._storage_profile_attribute_properties[attribute]
        storage_profile = self._get_storage_profile_for_backend(host_name,
                                                                *attribute_properties['backends'])
        if storage_profile:
            return attribute_properties['getter'](storage_profile)
        raise cmerror.CMError(str("Failed to get %s" % attribute))

    def _get_ceph_openstack_pg_proportion(self, host_name):
        return self._get_storage_profile_attribute(host_name, 'openstack_pg_proportion')

    def _get_ceph_caas_pg_proportion(self, host_name):
        return self._get_storage_profile_attribute(host_name, 'caas_pg_proportion')

    def _get_lvm_instance_storage_partitions(self, host_name):
        try:
            if self.instance_default_backend in SUPPORTED_INSTANCE_BACKENDS:
                return self._get_storage_profile_attribute(
                    host_name, 'lvm_instance_storage_partitions')
        except configerror.ConfigError:
            pass

        if self.instance_default_backend not in ALL_DEFAULT_INSTANCE_BACKENDS:
            raise cmerror.CMError(
                str("Unknown instance_default_backend %s "
                    "not supported" % self.instance_default_backend))
        return []

    def _get_lvm_cinder_storage_partitions(self, host_name):
        return self._get_storage_profile_attribute(host_name, 'lvm_cinder_storage_partitions')

    def _get_bare_lvm_mount_options(self, host_name):
        return self._get_storage_profile_attribute(host_name, 'mount_options')

    def _get_bare_lvm_mount_dir(self, host_name):
        return self._get_storage_profile_attribute(host_name, 'mount_dir')

    def _get_bare_lvm_lv_name(self, host_name):
        return self._get_storage_profile_attribute(host_name, 'lv_name')

    def _get_instance_lv_percentage(self, host_name):
        try:
            if self.instance_default_backend in SUPPORTED_INSTANCE_BACKENDS:
                return self._get_storage_profile_attribute(
                    host_name, 'lvm_instance_cow_lv_storage_percentage')
        except configerror.ConfigError:
            return DEFAULT_INSTANCE_LV_PERCENTAGE
        raise cmerror.CMError(str("Failed to found lvm from storage_profiles"))

    def _is_osd_host(self, name):
        try:
            return bool(name in self._hosts_config_handler.get_service_profile_hosts('storage'))
        except configerror.ConfigError:
            return False

    def _is_rbd_ceph_configured(self, host_name):
        return self._is_backend_configured('ceph', host_name)

    def _is_lvm_configured(self, host_name):
        return self._is_backend_configured('lvm', host_name)

    def _is_bare_lvm_configured(self, host_name):
        return self._is_backend_configured('bare_lvm', host_name)

    def _get_hw_type(self, name):
        hwmgmt_addr = self._hosts_config_handler.get_hwmgmt_ip(name)
        hwmgmt_user = self._hosts_config_handler.get_hwmgmt_user(name)
        hwmgmt_pass = self._hosts_config_handler.get_hwmgmt_password(name)
        hwmgmt_priv_level = self._hosts_config_handler.get_hwmgmt_priv_level(name)
        return hw.get_hw_type(hwmgmt_addr, hwmgmt_user, hwmgmt_pass, hwmgmt_priv_level)

    @staticmethod
    def _get_os_disk(hw_type):
        return hw.get_os_hd(hw_type)

    def _get_osd_disks_for_embedded_deployment(self, host_name):
        return self._hosts_config_handler.get_ceph_osd_disks(host_name)

    @staticmethod
    def _get_osd_disks(hw_type):
        return hw.get_hd_with_usage(hw_type, "osd")

    def _by_path_disks(self, hw_type, nr_of_disks):
        return self._get_osd_disks(hw_type)[0:nr_of_disks]

    @staticmethod
    def _is_by_path_disks(disk_list):
        return [disk for disk in disk_list if "by-path" in disk]

    def _get_physical_volumes(self, disk_list):
        partition_nr = "1"
        if self._is_by_path_disks(disk_list):
            return [disk+"-part"+partition_nr for disk in disk_list]
        else:
            return [disk+partition_nr for disk in disk_list]

    def _initialize_host_object(self, name):
        host = Host()
        host.name = name
        host.is_mgr = self._is_host_managment(host.name)
        host.is_controller = self._is_host_controller(host.name)
        host.is_compute = self._is_host_compute(host.name)
        host.is_storage = self._is_host_storage(host.name)
        host.is_rbd_ceph = self._is_rbd_ceph_configured(host.name)
        host.is_lvm = self._is_lvm_configured(host.name)
        host.is_bare_lvm = self._is_bare_lvm_configured(host.name)
        host.is_osd = self._is_osd_host(host.name)
        host.is_mon = host.is_mgr
        hw_type = self._get_hw_type(name)
        host.os_disk = self._get_os_disk(hw_type)
        if host.is_bare_lvm:
            partitions = self._get_lvm_instance_storage_partitions(host.name)
            host.bare_lvm_disks = self._by_path_disks(hw_type, len(partitions))
            host.bare_lvm_physical_volumes = self._get_physical_volumes(host.bare_lvm_disks)
            host.mount_options = self._get_bare_lvm_mount_options(host.name)
            host.mount_dir = self._get_bare_lvm_mount_dir(host.name)
            host.bare_lvm_lv_name = self._get_bare_lvm_lv_name(host.name)

        if host.is_compute and self.instance_default_backend != 'rbd':
            host.vg_percentage = INSTANCE_NODE_VG_PERCENTAGE

        if self.is_lvm_backend and host.is_controller:
            nr_of_cinder_disks = int(len(self._get_lvm_cinder_storage_partitions(host.name)))
            nr_of_nova_disks = int(len(self._get_lvm_instance_storage_partitions(host.name)))
            nr_of_all_disks = nr_of_cinder_disks + nr_of_nova_disks
            if nr_of_nova_disks > 0:
                host.cinder_disks = \
                    self._by_path_disks(hw_type, nr_of_all_disks)[-nr_of_cinder_disks:]
            else:
                host.cinder_disks = self._by_path_disks(hw_type, nr_of_cinder_disks)
            host.cinder_physical_volumes = self._get_physical_volumes(host.cinder_disks)

        if host.is_rbd_ceph:
            nr_of_osd_disks = self._get_nr_of_ceph_osd_disks(host.name)
            if self._caas_config_handler.is_vnf_embedded_deployment():
                host.ceph_osd_disks = \
                    self._get_osd_disks_for_embedded_deployment(host.name)[0:nr_of_osd_disks]
            else:
                host.ceph_osd_disks = self._get_osd_disks(hw_type)[0:nr_of_osd_disks]
            host.osd_disks_ids = range(1, nr_of_osd_disks+1)

        if host.is_lvm and host.is_compute:
            partitions = self._get_lvm_instance_storage_partitions(host.name)
            host.instance_disks = self._by_path_disks(hw_type, len(partitions))
            host.instance_physical_volumes = self._get_physical_volumes(host.instance_disks)
            host.instance_lv_percentage = self._get_instance_lv_percentage(host.name)
        return host
