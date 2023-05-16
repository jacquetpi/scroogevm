from model.sliceobjectwrapper import SliceObjectWrapper
from model.slicehost import SliceHost
from model.stability_assesser.stabilityassesserlstm import StabilityAssesserLstm
from model.oversubscription_computation.nodebasedoversubscription import NodeBasedOversubscriptionComputation
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
        previous_slice = self.get_nth_to_last_slice(1)
        if previous_slice == None: return True
        for vm in self.get_last_slice().get_vm_list():
            if not previous_slice.is_vm_in(vm):
                return True
        return False

    def compute_stability(self, slice_to_be_added : SliceHost):
        if self.strategy != "scroogevm":
            return True, True
            
        if not self.is_historical_full():
            return False, False

        assesser = StabilityAssesserLstm()
        cpu_stability = assesser.assess_form_slice_list(slice_list=self.slice_object_list, new_slice=slice_to_be_added, metric='cpu_usage', max_config=slice_to_be_added.get_cpu_config())
        mem_stability = assesser.assess_form_slice_list(slice_list=self.slice_object_list, new_slice=slice_to_be_added, metric='mem_usage', max_config=slice_to_be_added.get_mem_config())
        return cpu_stability, mem_stability  

    def get_cpu_mem_tiers(self,  computation : NodeBasedOversubscriptionComputation): # return cpu_tier0, cpu_tier1, mem_tier0, mem_tier1
        computation.set_context(self)
        cpu_tier0, cpu_tier1 = computation.compute_cpu_tiers()
        mem_tier0, mem_tier1 = computation.compute_mem_tiers()
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