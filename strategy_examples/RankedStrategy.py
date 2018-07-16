#!/usr/bin/env python3
"""
Module for ranged strategy
"""
from pprint import pprint as pp
import datetime
import logging
import sys
import smartsched.common as common
import smartsched.daemon.base_strategy as base_strategy


class RankedStrategy(base_strategy.BaseStrategy):

    def __init__(self, config):
        base_strategy.BaseStrategy.__init__(self, config)
        self.sleep_time = 3700 # Sleep time is slightly more than an hour 
        self.IM_MAD_OVZ_ID = 'im_ovz' # Only for OpenVZ
        self.cluster_list = []

        self.min_lifetime = int(config['min_lifetime'])
        self.sleep_time = int(config['sleep_time'])
        if self.sleep_time < self.min_lifetime:
            self.sleep_time = self.min_lifetime + 100
            self.logger.warning('sleep_time is less than min_lifetime. I will use min_lifetime + 100 as a sleep_time')
        self.cluster_list = [int(x) for x in config['cluster_list'].split(',')]
        self.psquare = float(config['psquare'])

        # Get parameters
        self.cpu_max_ovc_0 = float(config['cpu_max_ovc_0'])
        self.mem_max_ovc_0 = float(config['mem_max_ovc_0'])
        self.cpu_max_usage_0 = float(config['cpu_max_usage_0'])
        self.mem_max_usage_0 = float(config['mem_max_usage_0'])
        self.cpu_max_ovc_1 = float(config['cpu_max_ovc_1'])
        self.mem_max_ovc_1 = float(config['mem_max_ovc_1'])
        self.cpu_max_usage_1 = float(config['cpu_max_usage_1'])
        self.mem_max_usage_1 = float(config['mem_max_usage_1'])

        sl = common.StreamToLogger(self.logger, logging.INFO)
        sys.stdout = sl

        sl = common.StreamToLogger(self.logger, logging.ERROR)
        sys.stderr = sl

        self.cloud = common.get_cloud_handler()
        self.monitoring = common.get_monitoring_handler()

        self.hosts = []
        self.vms = []
        self.clusters = []
        self.initial_rank = 0

    def get_ovz_hosts_ids(self):
        """ Returns list if ovz host ids in allowd clusters."""
        all_hosts = []
        for cluster_id in self.cluster_list:
            all_hosts = self.cloud.get_hosts_of_cluster(cluster_id)
        ovz_hosts_ids = set()
        for host in all_hosts:
            if host['im_mad'] == self.IM_MAD_OVZ_ID:
                ovz_hosts_ids.add(host['id'])
        return ovz_hosts_ids

    def get_running_vms_on_hosts(self, hosts_ids):
        """ Return vms running on the hosts ids listed in host_ids.
        Checks if vm is running right now (not stopped): start_time > end_time """
        vms = self.cloud.get_vms_repr()
        vms_on_hosts = []
        for vm in vms:
            if (vm['retime'] < vm['rstime']) and vm['hid'] in hosts_ids:
                vms_on_hosts.append(vm)
        return vms_on_hosts

    def give_class_to_vms(self):
        for vm in self.vms:
            vm['lifetime'] = datetime.datetime.utcnow() - vm['rstime']
            if vm['lifetime'].total_seconds() < self.min_lifetime:
                vm['class'] = 2
                continue
            current_mon = self.monitoring.get_ovz_vm(vm['id'], ['mem', 'cpu', 'num_cpu'], limit=int(self.min_lifetime/60))
            # For current vm get max, min and average CPU and MEM usage ratio:
            # 0 <= ratio <= 1
            mem_min = 10000
            mem_max = -1
            cpu_min = 1000
            cpu_max = -1

            mem_cumulative = 0
            cpu_cumulative = 0
            probes_count = 0

            corrupted = 0
            for row in current_mon:
                # Some probes are corrupted. We need to ignore them.
                if 'cpu' not in row or 'mem' not in row or 'num' not in row:
                    corrupted += 1
                    continue
                probes_count += 1

                # Sometimes number of cores is equal to 0 which is wrong. We do not rely on that
                # metric so we can ignore it. It happens if VM require a fraction of a core,
                # like 0.3 core.
                if row['num'] == 0:
                    row['num'] = vm['cpu_allocated']

                cpu_percent = row['cpu'] / row['num'] / 100.0
                if row['mem'] < mem_min:
                    mem_min = row['mem']
                if row['mem'] > mem_max:
                    mem_max = row['mem']
                if cpu_percent < cpu_min:
                    cpu_min = cpu_percent
                if cpu_percent > cpu_max:
                    cpu_max = cpu_percent

                mem_cumulative += row['mem']
                cpu_cumulative += cpu_percent

            mem_avg = 0.01 * mem_cumulative / probes_count # Mem is measured in 0.0 < 100.0 range
            mem_min = 0.01 * mem_min
            mem_max = 0.01 * mem_max

            cpu_avg = 1.0 * cpu_cumulative / probes_count  # CPU is measured in 0.0 < 1.0 range
            
            vm['mem_min'] = mem_min
            vm['cpu_min'] = cpu_min
            vm['mem_max'] = mem_max
            vm['cpu_max'] = cpu_max
            vm['mem_avg'] = mem_avg
            vm['cpu_avg'] = cpu_avg
            vm['class'] = 0
            # So when min, max and average consumption is received we can use two of them as an
            # input for calculating P * P - the distance between (0, 0) point and point
            # representing the VM on the plot with axes CPU usage, MEM usage.
            p = mem_avg * mem_avg + cpu_avg * cpu_avg # Here we use average
            if p > self.psquare:
                vm['class'] = 1
            if p <= self.psquare:
                vm['class'] = 0

    def get_vm(self, vm_id):
        """Function to get vm from list of vms"""
        for vm in self.vms:
            if vm['id'] == vm_id:
                return vm
        self.logger.info('No vm found with id ' + str(vm_id))
        return self.cloud.get_vm_repr(vm_id)

    def get_hosts_classified(self, hosts_ids):
        """ Get hosts representation and get host's classes """
        hosts = []
        for host_id in list(hosts_ids):
            host = self.cloud.get_host_repr(host_id)
            count = {0: 0, 1: 0, 2: 0}
            for vm_id in host['vms']:
                vm = self.get_vm(int(vm_id))
                if vm['lcm_state'] != 'RUNNING':
                    vm['class'] = 2
                if 'class' in vm.keys():
                    count[vm['class']] += 1
                else:
                    count[2] += 1
            host['count'] = count
            # host['class'] = get_host_class(host)
            hosts.append(host)
        return hosts

    def get_initial_rank(self):
        total_0 = sum([host['count'][0] for host in self.hosts])
        total_1 = sum([host['count'][1] for host in self.hosts])
        print('Amount of 0: {0},\tAmount if 1: {1}'.format(total_0, total_1))
        initial_rank = 0
        if total_0 < total_1:
            initial_rank = 1
        return initial_rank

    def calculate_host_avg_usage(self):
        for host in self.hosts:
            tmp_mem_used = 0
            tmp_cpu_used = 0
            for vm_id in host['vms']:
                vm = self.get_vm(int(vm_id))
                #if 'class' in vm.keys() and vm['class'] < 2:
                if vm['retime'] < vm['rstime']:
                    tmp_mem_used += int(vm['mem_avg'] * vm['mem_allocated'])
                    tmp_cpu_used += int(vm['cpu_avg'] * vm['cpu_allocated'])
            host['usage_mem']['used_avg'] = tmp_mem_used
            host['usage_cpu']['used_avg'] = tmp_cpu_used

    def form_rank_clusters(self):
        clusters = {0:[], 1:[], 2:[]}
        mem_requested = {0: 0, 1: 0, 2: 0}
        cpu_requested = {0: 0, 1: 0, 2: 0}

        for vm in self.vms:
            mem_requested[vm['class']] += vm['mem_allocated']
            cpu_requested[vm['class']] += vm['cpu_allocated']

        another_rank = (self.initial_rank + 1) % 2
        # Sort hosts by amount of initial rank in reversed order.
        # It allows to make less migrations later.
        self.hosts.sort(key=lambda x: x['count'][self.initial_rank], reverse=True)
        for host in self.hosts:
            if mem_requested[self.initial_rank] > 0 or cpu_requested[self.initial_rank] > 0:
                mem_requested[self.initial_rank] -= host['usage_mem']['max'] * (self.mem_max_ovc_0 if self.initial_rank == 0 else self.mem_max_ovc_1)
                cpu_requested[self.initial_rank] -= host['usage_cpu']['max'] * (self.cpu_max_ovc_0 if self.initial_rank == 0 else self.cpu_max_ovc_1)
                clusters[self.initial_rank].append(host)
            elif mem_requested[another_rank] > 0 or cpu_requested[another_rank] > 0:
                mem_requested[another_rank] -= host['usage_mem']['max'] * (self.mem_max_ovc_0 if another_rank == 0 else self.mem_max_ovc_1)
                cpu_requested[another_rank] -= host['usage_cpu']['max'] * (self.cpu_max_ovc_0 if another_rank == 0 else self.cpu_max_ovc_1)
                clusters[another_rank].append(host)
            else:
                clusters[2].append(host)

        self.logger.info(str(len(clusters[0])) + ' ' + str(len(clusters[1])) + ' ' + str(len(clusters[2])))
        return clusters

    def add_temporary_host_usages(self):
        for host in self.hosts:
            host['vms_v'] = []
            for vm_id in host['vms']:
                host['vms_v'].append(vm_id)
            host['usage_mem_v'] = host['usage_mem'].copy()
            host['usage_cpu_v'] = host['usage_cpu'].copy()

    def check_migration(self, vm, host, original_host):
        if vm['class'] not in [0, 1]:
            return False
        mem_allocated = host['usage_mem_v']['allocated'] + vm['mem_allocated']
        cpu_allocated = host['usage_cpu_v']['allocated'] + vm['cpu_allocated']
        mem_used = host['usage_mem_v']['used_avg'] + vm['mem_avg'] * vm['mem_allocated']
        cpu_used = host['usage_cpu_v']['used_avg'] + vm['cpu_avg'] * vm['cpu_allocated']
        mem_usage_ratio = mem_used / host['usage_mem_v']['max']
        cpu_usage_ratio = cpu_used / host['usage_cpu_v']['max']
        mem_overc_ratio = mem_allocated / host['usage_mem_v']['max']
        cpu_overc_ratio = cpu_allocated / host['usage_cpu_v']['max']

        isAllowed = True
        if vm['class'] == 0:
            if mem_overc_ratio > self.mem_max_ovc_0:
                isAllowed = False
            if cpu_overc_ratio > self.cpu_max_ovc_0:
                isAllowed = False
            if mem_usage_ratio > self.mem_max_usage_0:
                isAllowed = False
            if cpu_usage_ratio > self.cpu_max_usage_0:
                isAllowed = False

        if vm['class'] == 1:
            if mem_overc_ratio > self.mem_max_ovc_1:
                isAllowed = False
            if cpu_overc_ratio > self.cpu_max_ovc_1:
                isAllowed = False
            if mem_usage_ratio > self.mem_max_usage_1:
                isAllowed = False
            if cpu_usage_ratio > self.cpu_max_usage_1:
                isAllowed = False

        if isAllowed:
            host['usage_mem_v']['allocated'] = mem_allocated
            host['usage_cpu_v']['allocated'] = cpu_allocated
            host['usage_mem_v']['used_avg'] = mem_used
            host['usage_cpu_v']['used_avg'] = cpu_used
            host['usage_mem_v']['ratio_overc'] = mem_overc_ratio
            host['usage_cpu_v']['ratio_overc'] = cpu_overc_ratio
            host['usage_mem_v']['ratio_used'] = mem_usage_ratio
            host['usage_cpu_v']['ratio_used'] = cpu_usage_ratio

            print('Migrating VM ID:', vm['id'], ', ', original_host['id'], ' --> ', host['id'])
            host['vms_v'].append(str(vm['id']))
            print(original_host['vms_v'])
            original_host['vms_v'].remove(str(vm['id']))
            original_host['usage_mem_v']['allocated'] -= vm['mem_allocated']
            original_host['usage_cpu_v']['allocated'] -= vm['cpu_allocated']
            original_host['usage_mem_v']['used_avg'] -= vm['mem_avg'] * vm['mem_allocated']
            original_host['usage_cpu_v']['used_avg'] -= vm['cpu_avg'] * vm['cpu_allocated']
            original_host['usage_mem_v']['ratio_used'] = original_host['usage_mem_v']['used_avg'] / original_host['usage_mem_v']['max']
            original_host['usage_cpu_v']['ratio_used'] = original_host['usage_cpu_v']['used_avg'] / original_host['usage_cpu_v']['max']
            original_host['usage_mem_v']['ratio_overc'] = original_host['usage_mem_v']['allocated'] / original_host['usage_mem_v']['max']
            original_host['usage_cpu_v']['ratio_overc'] = original_host['usage_cpu_v']['allocated'] / original_host['usage_cpu_v']['max']
            return True
        return False

    def do_migrations(self):
        """ Do all possible migrations"""
        # Sort hosts in clusters in order to migrate from the busiest host
        for rank in self.clusters:
            self.clusters[rank].sort(key=lambda x: ((1-x['usage_mem']['used_avg'])*x['usage_mem']['max'], (1-x['usage_cpu']['used_avg'])*x['usage_cpu']['max']))

        # Start with migration of 0 rank
        for rank in [0, 1]:
            self.logger.info('Dealing with rank ' + str(rank))
            for host in self.clusters[rank]:
                self.logger.info('Migrating from host' + str(host['id']))
                candidates = []
                for vm_id in host['vms']:
                    vm = self.get_vm(int(vm_id))
                    if 'class' in vm.keys() and vm['class'] != rank:
                        candidates.append(vm)
                # In order to try to migrae big vms first
                candidates.sort(key=lambda x: (x['mem_allocated'], x['cpu_allocated']), reverse=True)
                for vm in candidates:
                    for dest_host in self.clusters[vm['class']]:
                        if self.check_migration(vm, dest_host, host):
                            migration = self.cloud.migrate(vm['id'], dest_host['id'], True, False)
                            self.logger.info(str(migration))
                            break

    def perform_strategy(self):
        hosts_ids = self.get_ovz_hosts_ids()
        self.vms = self.get_running_vms_on_hosts(hosts_ids)
        self.give_class_to_vms()
        self.hosts = self.get_hosts_classified(hosts_ids, )
        self.initial_rank = self.get_initial_rank()

        for host in self.hosts:
            self.logger.info('ID: {3}\t({4}/{5}) \tCPU Total: {0}  \tOVC: {1:.2f}\tReal: {2:.2f}'.format(host['usage_cpu']['max'], host['usage_cpu']['ratio_overc'], host['usage_cpu']['ratio_used'], host['id'], host['count'][0], host['count'][1]))
            self.logger.info('\t\tMEM Total: {0}  \tOVC: {1:.2f}\tReal: {2:.2f}'.format(host['usage_mem']['max'], host['usage_mem']['ratio_overc'], host['usage_mem']['ratio_used']))

        self.calculate_host_avg_usage()
        self.clusters = self.form_rank_clusters()
        self.add_temporary_host_usages()
        self.do_migrations()

        for rank in self.clusters:
            self.logger.info('Rank:' + str(rank))
            for host in self.clusters[rank]:
                self.logger.info('    Host ID: ' + str(host['id']))
                for vm_id in host['vms_v']:
                    vm = self.get_vm(int(vm_id))
                    self.logger.info('        VM ID: ' + str(vm['id']) + ' - ' + str(vm['class']) if 'class' in vm else '')

target_class = RankedStrategy
