from model.sliceobjectwrapper import SliceObjectWrapper
from model.sliceobject import SliceObject
from model.slicevm import SliceVm
from scipy.stats import ttest_ind_from_stats

class SliceVmWrapper(SliceObjectWrapper):

    def __init__(self, domain_name : str, historical_occurences : int, cpu_percentile : int, mem_percentile : int, aggregation : int):
        super().__init__(historical_occurences, cpu_percentile, mem_percentile, aggregation)
        self.domain_name=domain_name
        self.debug_cpu_reason = "=0 no prev data"
        self.debug_mem_reason = "=0 no prev data"

    def add_slice_data_from_raw(self, domain_data : dict):
        if(len(domain_data.keys()) == 0):
            print("Empty data on slice encountered on domain " + self.domain_name)
            return
        slice_vm = SliceVm(self.get_slice_object_from_raw(domain_data))
        self.compute_state_of_new_slice(slice_vm)
        self.add_slice(slice_vm)

    def add_slice_data_from_dump(self, vm_dump_data : dict, occurence : int, epoch : int):
        if(len(vm_dump_data.keys()) == 0):
            print("Empty data on slice encountered on dump " + self.domain_name)
            return
        slice_object = self.get_slice_object_from_dump(dump_data=vm_dump_data, occurence=occurence, epoch=epoch)
        if slice_object == None:
            return False # VM not started yet
        slice_vm = SliceVm(slice_object)
        if slice_vm == self.get_last_slice():
            self.is_ended = True
            return False
        self.add_slice(slice_vm)
        return True

    def is_vm_ended(self):
        if hasattr(self, 'is_ended'):
            return self.is_ended
        return False

    def get_cpu_mem_tiers(self):
        return 0,0,0,0 # Unused for the current paper. TODO: clean up
        cpu_tier0, cpu_tier1 = self.get_cpu_tiers()
        mem_tier0, mem_tier1 = self.get_mem_tiers()
        return cpu_tier0, cpu_tier1, mem_tier0, mem_tier1

    def __str__(self):
        if(len(self.slice_object_list)>0):
            cpu_tier0, cpu_tier1, mem_tier0, mem_tier1 = self.get_cpu_mem_tiers()
            cpu_state = self.get_last_slice().get_cpu_state()
            mem_state = self.get_last_slice().get_mem_state()
            return "SliceVmWrapper for " + self.domain_name + ": " +\
                 "cpu_state=" + str(cpu_state) + "(" + self.debug_cpu_reason + ") [" + str(round(cpu_tier0,1)) + ";" + str(round(cpu_tier1,1)) + "] " +\
                 "mem_state=" + str(mem_state) + "(" + self.debug_mem_reason + ") [" + str(round(mem_tier0,1)) + ";" + str(round(mem_tier1,1)) + "]"
        else:
            return "SliceVmWrapper for " + self.domain_name + ": no data"

    # # VM tiers as threshold
    # def get_cpu_tiers(self): # return tier0, tier1
    #     if self.get_last_slice().is_cpu_tier_defined():
    #         return self.get_last_slice().get_cpu_tiers()
    #     # Main algorithm
    #     cpu_state = self.get_last_slice().get_cpu_state()
    #     if cpu_state == 0:
    #         cpu_tier0 = self.get_last_slice().get_cpu_config()
    #         cpu_tier1 = self.get_last_slice().get_cpu_config()
    #     elif cpu_state == 1:
    #         cpu_tier0 = self.round_to_upper_nearest(x=self.get_slices_max_metric(cpu_percentile=95), nearest_val=0.50) # unity is vcpu
    #         cpu_tier1 = self.get_last_slice().get_cpu_config()
    #     else:
    #         cpu_tier0 = self.round_to_upper_nearest(x=self.get_slices_max_metric(metric='cpu_avg'), nearest_val=0.50)
    #         cpu_tier1 = self.round_to_upper_nearest(x=self.get_slices_max_metric(cpu_percentile=95), nearest_val=0.50)
    #     self.get_last_slice().update_cpu_tiers(cpu_tier0, cpu_tier1)
    #     return cpu_tier0, cpu_tier1

    # # VM tiers as threshold
    # def get_mem_tiers(self): # return tier0, tier1
    #     if self.get_last_slice().is_mem_tier_defined():
    #         return self.get_last_slice().get_mem_tiers()
    #     # Main algorithm
    #     mem_state = self.get_last_slice().get_mem_state()
    #     if mem_state == 0:
    #         mem_tier0 = self.get_last_slice().get_mem_config()
    #         mem_tier1 = self.get_last_slice().get_mem_config()
    #     elif mem_state == 1:
    #         mem_tier0 = self.round_to_upper_nearest(x=self.get_slices_max_metric(mem_percentile=95), nearest_val=256) # unity is MB
    #         mem_tier1 = self.get_last_slice().get_mem_config()
    #     else:
    #         mem_tier0 = self.round_to_upper_nearest(x=self.get_slices_max_metric(metric='mem_avg'), nearest_val=256)
    #         mem_tier1 = self.round_to_upper_nearest(x=self.get_slices_max_metric(mem_percentile=95), nearest_val=256)
    #     self.get_last_slice().update_mem_tiers(mem_tier0, mem_tier1)
    #     return mem_tier0, mem_tier1