#!/usr/bin/env python3

from datetime import timedelta
from datetime import datetime
import time

import logging
import smartsched.daemon.base_strategy as base_strategy
import smartsched.common as common

CPU_MAX_OVC_RATIO = 3
MEM_MAX_OVC_RATIO = 2
# If or memory is used more than USAGE_RATIO - ignore it
CPU_MAX_USAGE_RATIO = 50
MEM_MAX_USAGE_RATIO = 30

# Waiting time for machine deploy
TIME_COUNT_MAX = 600

RESOLVED_STATES = ['RUNNING', 'FAILURE']

class PlacePendingStrategy(base_strategy.BaseStrategy):
    
    # Matrix for all possible deployments of all pending VMs
    deploy_mesh = []

    isDeploying = False
    current_vm = None
    current_host = None
    # Count deploy time and compare with TIME_COUNT_MAX
    deploying_time_count = 0

    def __init__(self, config):
        base_strategy.BaseStrategy.__init__(self, config)
        self.sleep_time = 10
        self.cluster_list = []

        self.sleep_time = int(config['sleep_time'])
        self.cluster_list = [int(x) for x in config['cluster_list'].split(',')]
        self.logger = logging.getLogger('PlacePending')
        self.logger.setLevel(logging.INFO)
        fh = logging.FileHandler('/root/PlacePending.log')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

        self.cloud = common.get_cloud_handler()
        self.influx_handler = common.get_monitoring_handler()

    def perform_strategy(self):
        if self.deploy_mesh == [] and not self.isDeploying:
            self.logger.info('Build deploy mesh')
            self.build_deploy_mesh()
            return

        if self.deploy_mesh != [] and not self.isDeploying:
            self.logger.info('Try to deploy vm')
            self.try_deploy()
            return

        if self.isDeploying:
            self.logger.info('Check deploying process')
            self.check_deploy()
            return

    def build_deploy_mesh(self):
        pending_vm_list = self.cloud.get_pending_unscheduled()
        self.logger.info('There are ' + str(len(pending_vm_list)) + ' pending machines')
        for vm in pending_vm_list:
            if not vm['cluster_id']: # if clusters is None
                self.logger.info(str(vm['id']) + ' Have no cluster information')
                continue
            if (len(self.cluster_list) != 0) and (vm['cluster_id'][0] not in self.cluster_list):
                self.logger.info(str(vm['id']) + ' is not on allowed cluster')
                continue
            hosts = self.cloud.get_hosts_of_cluster(vm['cluster_id'])
            host_candidates = []
            for host in hosts:
                # Get logs of CPU and MEM, usage and load
                host_cpu_usage_log = self.influx_handler.get_host_load(host['name'], 'host_cpu_load', period='5m', group_by='10m', aggregation='max')
                host_mem_usage_log = self.influx_handler.get_host_load(host['name'], 'host_mem_used_percent',  period='5m', group_by='10m', aggregation='max')
                host_cpu_total_log = self.influx_handler.get_host_load(host['name'], 'host_cpu_count', period='5m', group_by='10m', aggregation='last')
                host_mem_total_log = self.influx_handler.get_host_load(host['name'], 'host_mem_total_bytes', period='5m', group_by='10m', aggregation='last')
                # Get current total value and "Worst case" usage
                host_cpu_usage = max([host_cpu_usage_log[x] for x in host_cpu_usage_log])
                host_mem_usage = max([host_mem_usage_log[x] for x in host_mem_usage_log])
                host_cpu_total = host_cpu_total_log[max(host_cpu_total_log.keys())]
                host_mem_total = host_mem_total_log[max(host_mem_total_log.keys())]

                host_cpu_used = host_cpu_usage / 100.0 * host_cpu_total
                host_mem_used = host_mem_usage / 100.0 * host_mem_total
                host_cpu_free = host_cpu_total - host_cpu_used
                host_mem_free = host_mem_total - host_mem_used

                # Get data about new VMs
                fresh_vms = []
                for running_vm in host['vms']:
                    if running_vm['rstime'] != datetime(1970, 1, 1, 0, 0):
                        if datetime.utcnow() - running_vm['rstime'] < timedelta(hours=5):
                            fresh_vms.append(running_vm)
                # Correct host CPU and MEM usage for new VMs (let it be MAX)
                for running_vm in fresh_vms:
                    host_cpu_usage += 1.0 * running_vm['cpu_allocated'] / host['usage_cpu']['max']
                    host_mem_usage += 1.0 * running_vm['mem_allocated'] / host['usage_mem']['max']

                host_cpu_ovc_expected = host['usage_cpu']['ratio_overc'] + vm['cpu_allocated'] / host['usage_cpu']['max']
                host_mem_ovc_expected = host['usage_mem']['ratio_overc'] + vm['mem_allocated'] / host['usage_mem']['max']

                if vm['cpu_req'] > host_cpu_free:
                    self.logger.info('{_hostname} lack of CPU'.format(_hostname=host['name']))
                    continue
                if vm['mem_req'] * 1024.0 > host_mem_free:
                    self.logger.info('{_hostname} lack of MEM'.format(_hostname=host['name']))
                    continue

                isHostFree = True
                if host_cpu_usage > CPU_MAX_USAGE_RATIO:
                    # self.logger.info('CPU Usage - already exceeded for ' + host['name'])
                    isHostFree = False
                if host_mem_usage > MEM_MAX_USAGE_RATIO:
                    # self.logger.info('MEM Usage - already exceeded for ' + host['name'])
                    isHostFree = False
                if host_cpu_ovc_expected > CPU_MAX_OVC_RATIO:
                    # self.logger.info('CPU Overcommit - will be exceeded for {_hostname}: {_ovc_expected} > {_ovc_max}'.format(
                    #     _hostname=host['name'],
                    #     _ovc_expected=host_cpu_ovc_expected,
                    #     _ovc_max=CPU_MAX_OVC_RATIO
                    # ))
                    isHostFree = False
                if host_mem_ovc_expected > MEM_MAX_OVC_RATIO:
                    # self.logger.info('MEM Overcommit - will be exceeded for {_hostname}: {_ovc_expected} > {_ovc_max}'.format(
                    #     _hostname=host['name'],
                    #     _ovc_expected=host_mem_ovc_expected,
                    #     _ovc_max=MEM_MAX_OVC_RATIO
                    # ))
                    isHostFree = False

                if isHostFree:
                    host_candidates.append(host)

            if len(host_candidates) != 0:
                self.deploy_mesh.append({'vm':vm, 'hosts':host_candidates})
            else:
                self.logger.info("No free hosts for vm " + str(vm['id']))

    def try_deploy(self):
        self.current_vm = self.deploy_mesh[0]['vm']
        self.current_host = self.deploy_mesh[0]['hosts'][0]

        self.logger.info('Try deploy VM {_vm_id} deployed on {_hostname}'.format(_vm_id=self.current_vm['id'], _hostname=self.current_host['name']))
        self.cloud.deploy(self.current_vm['id'], self.current_host['id'], False)
        self.isDeploying = True
        self.deploying_time_count = 0


    def check_deploy(self):
        self.deploying_time_count += self.sleep_time
        deployed_vm = self.cloud.get_vms_repr(startId=self.current_vm['id'], endId=self.current_vm['id'], vmStateFilter=-2)[0]
        self.logger.info('Status: {}'.format(deployed_vm['lcm_state']))
        if deployed_vm['lcm_state'] == 'RUNNING':
            self.isDeploying = False
            self.deploy_mesh = []
            self.logger.info('Deploy successful for vm: ' + str(self.current_vm['id']))
            return
        
        if deployed_vm['state'] == 'FAILED' or deployed_vm['lcm_state'] == 'FAILURE':
            self.isDeploying = False
            self.deploy_mesh = []
            self.logger.error('Failed to deploy vm: ' + str(self.current_vm['id']))
            return
        if self.deploying_time_count > TIME_COUNT_MAX:
            self.isDeploying = False
            self.deploy_mesh = []
            self.logger.error('Deploy Timeout for vm: ' + str(self.current_vm['id']))
            return

target_class = PlacePendingStrategy

