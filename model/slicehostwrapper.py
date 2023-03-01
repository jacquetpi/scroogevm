from model.sliceobjectwrapper import SliceObjectWrapper
from model.slicehost import SliceHost
from model.stabilityassesserlstm import StabilityAssesserLstm
from model.oversubscriptioncomputation import GreedyOversubscriptionComputation
from model.oversubscriptioncomputation import PercentileOversubscriptionComputation
from model.oversubscriptioncomputation import DoaOversubscriptionComputation
from datetime import datetime
import numpy as np

class SliceHostWrapper(SliceObjectWrapper):

    def __init__(self, host_name : str, historical_occurences : int, cpu_percentile : int, mem_percentile : int, strategy : str, aggregation : int):
        super().__init__(historical_occurences, cpu_percentile, mem_percentile, aggregation)
        self.host_name=host_name
        self.strategy=strategy

    def add_slice_data_from_raw(self, host_data : dict):
        if(len(host_data.keys()) == 0):
            print("Empty data on slice encountered on host " + self.host_name)
            return
        slice_host = SliceHost(slice_object=self.get_slice_object_from_raw(host_data),
                        vm_list=host_data["vm"], booked_cpu=host_data["booked_cpu"], booked_mem=host_data["booked_mem"])
        cpu_stability, mem_stability = self.compute_stability(slice_to_be_added=slice_host)
        slice_host.set_stability(cpu_stability, mem_stability)
        self.add_slice(slice_host)

    def add_slice_data_from_dump(self, dump_data : dict, occurence : int):
        if(len(dump_data.keys()) == 0):
            print("Empty data on slice encountered on dump " + self.host_name)
            return
        slice_host = SliceHost(slice_object=self.get_slice_object_from_dump(dump_data=dump_data["node"], occurence=occurence, epoch=dump_data["epoch"][occurence]),
                        vm_list=dump_data["node"]["raw_data"][occurence]['vm'], booked_cpu=dump_data["node"]["booked_cpu"], booked_mem=dump_data["node"]["booked_mem"])
        cpu_stability, mem_stability = self.compute_stability(slice_to_be_added=slice_host)
        slice_host.set_stability(cpu_stability, mem_stability)
        self.add_slice(slice_host)

    def get_host_config(self):
        cpu_config_list = self.get_slices_metric("cpu_config")
        mem_config_list = self.get_slices_metric("mem_config")
        if cpu_config_list:
            cpu_config = cpu_config_list[-1]
        else:
            cpu_config=-1
        if mem_config_list:
            mem_config = mem_config_list[-1]
        else:
            mem_config=-1
        return cpu_config, mem_config

    def get_host_average(self):
        cpu_usage_list = self.get_slices_metric("cpu_avg")
        mem_usage_list = self.get_slices_metric("mem_avg")
        return np.average(cpu_usage_list), np.average(mem_usage_list)

    def get_host_percentile(self):
        cpu_usage_list = self.get_slices_metric(cpu_percentile=self.cpu_percentile)
        mem_usage_list = self.get_slices_metric(mem_percentile=self.mem_percentile)
        return np.max(cpu_usage_list), np.max(mem_usage_list)

    def does_last_slice_contain_a_new_vm(self):
        # VM name is supposed unique
        for vm in self.get_last_slice().get_vm_list():
            if not self.get_oldest_slice().is_vm_in(vm):
                return True
        return False

    def compute_stability(self, slice_to_be_added : SliceHost):
        if self.strategy != "greedy":
            return True, True
            
        if not self.is_historical_full():
            return False, False
        # dict_keys(['time', 'cpi', 'cpu', 'cpu_time', 'cpu_usage', 'elapsed_cpu_time', 'elapsed_time', 'freq', 'hwcpucycles', 'hwinstructions', 'maxfreq', 'mem', 'mem_usage', 'minfreq', 'oc_cpu', 'oc_cpu_d', 'oc_mem', 'oc_mem_d', 'sched_busy', 'sched_runtime', 'sched_waittime', 'swpagefaults', 'vm_number', 'vm'])
        current_data = list()
        index=0
        while True:
            slice = self.get_slice(index)
            if slice is None:
                break
            x = dict()
            x["time"] = slice.get_raw_metric("time")
            x["cpu_usage"] = slice.get_raw_metric("cpu_usage")
            x["mem_usage"] = slice.get_raw_metric("mem_usage")
            current_data.append(x)
            index+=1

        new_data = dict()
        new_data["time"] = [x for x in slice_to_be_added.get_raw_metric("time")]
        new_data["cpu_usage"] = slice_to_be_added.get_raw_metric("cpu_usage")
        new_data["mem_usage"] = slice_to_be_added.get_raw_metric("mem_usage")

        assesser = StabilityAssesserLstm()
        cpu_stability = assesser.assess(traindata_as_list=current_data, targetdata=new_data, metric="cpu_usage", max_value_config=slice_to_be_added.get_cpu_config())
        mem_stability = assesser.assess(traindata_as_list=current_data, targetdata=new_data, metric="mem_usage", max_value_config=slice_to_be_added.get_mem_config())
        return cpu_stability, mem_stability  

    def __get_chosen_oversubscription_computation(self):
        if self.strategy == "percentile":
            return PercentileOversubscriptionComputation(object_wrapper=self,cpu_percentile=self.cpu_percentile,mem_percentile=self.mem_percentile)
        elif self.strategy == "doa":
            return DoaOversubscriptionComputation(object_wrapper=self)
        else:
            return GreedyOversubscriptionComputation(object_wrapper=self,cpu_percentile=self.cpu_percentile,mem_percentile=self.mem_percentile)

    # Host tiers as threshold
    def get_cpu_tiers(self): # return tier0, tier1
        computation = self.__get_chosen_oversubscription_computation()
        cpu_tier0, cpu_tier1 = computation.compute_cpu_tiers()
        return cpu_tier0, cpu_tier1

    # Mem tiers as threshold
    def get_mem_tiers(self): # return tier0, tier1
        computation = self.__get_chosen_oversubscription_computation()
        mem_tier0, mem_tier1 = computation.compute_mem_tiers()
        return mem_tier0, mem_tier1

    def get_cpu_mem_tiers(self): # return cpu_tier0, cpu_tier1, mem_tier0, mem_tier1
        last_slice = self.get_last_slice()
        cpu_tier0, cpu_tier1 = self.get_cpu_tiers()
        mem_tier0, mem_tier1 = self.get_mem_tiers()
        return cpu_tier0, cpu_tier1, mem_tier0, mem_tier1

    def __str__(self):
        if(len(self.slice_object_list)>0):
            cpu_config, mem_config = self.get_host_config()
            cpu_avg, mem_avg = self.get_host_average()
            cpu_percentile, mem_percentile = self.get_host_percentile()
            return "SliceHostWrapper for " + self.host_name + " hostcpu avg/percentile/config " +\
                str(round(cpu_avg,1)) + "/" + str(round(cpu_percentile,1)) + "/" + str(int(cpu_config)) + " mem avg/percentile/config " +\
                str(round(mem_avg,1)) + "/" + str(round(mem_percentile,1)) + "/" + str(int(mem_config))
        else:
            return "SliceHostWrapper for " + self.host_name + ": no data"