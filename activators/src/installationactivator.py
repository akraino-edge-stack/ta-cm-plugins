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

from cmframework.apis import cmerror
from cmframework.apis import cmactivator
from cmdatahandlers.api import configmanager
from cmdatahandlers.api import configerror
import os
import subprocess
import json
import pwd
import logging

class installationactivator(cmactivator.CMGlobalActivator):
    inventory_cli = '/opt/cmframework/scripts/inventory.sh'
    playbooks_generate_cli = '/usr/local/bin/cmcli ansible-playbooks-generate'
    playbooks_path = '/opt/openstack-ansible/playbooks/'
    setup_playbook = 'setup-playbook.yml'
    presetup_playbook = 'presetup-playbook.yml'
    bootstrapping_playbook = 'bootstrapping-playbook.yml'
    provisioning_playbook = 'provisioning-playbook.yml'
    postconfig_playbook = 'postconfig-playbook.yml'
    state_file = '/etc/installation_state'

    def __init__(self):
        self.plugin_client = None

    def get_subscription_info(self):
        return '.*'

    def activate_set(self, props):
        self.activate_full()

    def activate_delete(self, props):
        self.activate_full()

    def activate_full(self, target=None):
        try:
            properties = self.get_plugin_client().get_properties('.*')
            if not properties:
                return
            propsjson = {}
            for name, value in properties.iteritems():
                try:
                    propsjson[name] = json.loads(value)
                except Exception as exp:
                    continue
            configman = configmanager.ConfigManager(propsjson)

            hostsconfig = configman.get_hosts_config_handler()
            installation_host = hostsconfig.get_installation_host()

            installed = False
            try:
                configman.get_cloud_installation_date()
                installed = True
            except configerror.ConfigError as exp:
                pass

            if installed:
                return

            usersconf = configman.get_users_config_handler()
            admin = usersconf.get_admin_user()

            #generate high level playbooks
            if self._run_cmd(self.playbooks_generate_cli, '/etc', 'root', os.environ.copy()):
                raise cmerror.CMError('Failed to run %s' % self.playbooks_generate_cli)

            caas_data = configman.get_caas_config_handler()
            phase = self._get_installation_phase()
            #first we run the setup 
            if not phase:
                self._set_installation_phase('setup-started')
                phase = 'setup-started'
            env = os.environ.copy()
            if phase == 'setup-started':
                env['VNF_EMBEDDED_DEPLOYMENT'] = 'false'
                env['CONFIG_PHASE'] = 'setup'
                env['BOOTSTRAP_OPTS'] = 'installation_controller=%s' %(installation_host)
                self._run_setup_playbook(self.presetup_playbook, env)
                env['BOOTSTRAP_OPTS'] = ''
                if caas_data.get_vnf_flag():
                    env['VNF_EMBEDDED_DEPLOYMENT'] = 'true'
                self._run_setup_playbook(self.setup_playbook, env)
                self._set_installation_phase('setup-ended')
                phase = 'setup-ended'

            #second we run the aio
            if phase == 'setup-ended':
                self._set_installation_phase('bootstrapping-started')
                phase = 'bootstrapping-started'
            if phase == 'bootstrapping-started':
                env['CONFIG_PHASE'] = 'bootstrapping'
                self._run_playbook(self.bootstrapping_playbook, admin, env)
                self._set_installation_phase('bootstrapping-ended')
                phase = 'bootstrapping-ended'

            #3rd we run the provisioning
            if phase == 'bootstrapping-ended':
                self._set_installation_phase('provisioning-started')
                phase = 'provisioning-started'
            if phase == 'provisioning-started':
                env['CONFIG_PHASE'] = 'provisioning'
                self._run_playbook(self.provisioning_playbook, admin, env)
                self._set_installation_phase('provisioning-ended')
                phase = 'provisioning-ended'

            #4th we run the postconfig
            if phase == 'provisioning-ended':
                self._set_installation_phase('postconfig-started')
                phase = 'postconfig-started'
            if phase == 'postconfig-started':
                env['CONFIG_PHASE'] = 'postconfig'
                env['CAAS_ONLY_DEPLOYMENT'] = 'false'
                if caas_data.get_caas_only():
                    env['CAAS_ONLY_DEPLOYMENT'] = 'true'
                self._run_playbook(self.postconfig_playbook, admin, env)
                self._set_installation_phase('postconfig-ended')
                phase = 'postconfig-ended'
            
            self._set_installation_date()

            self._set_state('success')

        except Exception as exp:
            self._set_state('failure')
            raise cmerror.CMError(str(exp))

    def _set_installation_phase(self, phase):
        self.get_plugin_client().set_property('cloud.installation_phase', json.dumps(phase))

    def _get_installation_phase(self):
        phase = None
        try:
            phase = json.loads(self.get_plugin_client().get_property('cloud.installation_phase'))
            logging.debug('Current installation phase cloud.installation_phase="%s"'%phase)
        except Exception as exp:
            pass
        return phase

    def _set_installation_date(self):
        from time import gmtime, strftime
        # Use ISO 8601 date format
        times = strftime('%Y-%m-%dT%H:%M:%SZ', gmtime())
        self.get_plugin_client().set_property('cloud.installation_date', json.dumps(times))

    def _run_playbook(self, playbook, user, env):
        cmd = '/usr/local/bin/openstack-ansible -b -u ' + user + ' ' + playbook
        result = self._run_cmd(cmd, self.playbooks_path, user, env)
        if result != 0:
            raise cmerror.CMError('Playbook %s failed' % playbook)
        
    def _run_setup_playbook(self, playbook, env):
        cmd = '/usr/local/bin/setup-controller.sh ' + playbook
        result = self._run_cmd(cmd, self.playbooks_path, 'root', env)
        if result != 0:
            raise cmerror.CMError('Playbook %s failed' % playbook)
        
    def _run_cmd(self, cmd, cwd, user, env):
        args = cmd.split()
        pw_record = pwd.getpwnam(user)
        user_name = pw_record.pw_name
        user_home_dir = pw_record.pw_dir
        user_uid = pw_record.pw_uid
        user_gid = pw_record.pw_gid
        env['HOME'] = user_home_dir
        env['LOGNAME'] = user_name
        env['HOME'] = user_home_dir
        env['PWD'] = cwd
        env['USER'] = user_name
        process = subprocess.Popen(args, preexec_fn=self._demote(user_uid, user_gid), cwd=cwd, env=env)
        result = process.wait()
        return result


    def _demote(self, user_uid, user_gid):
        def result():
            os.setgid(user_gid)
            os.setuid(user_uid)
        return result

    def _set_state(self, state):
        with open(self.state_file, 'w') as f:
            f.write(state)
