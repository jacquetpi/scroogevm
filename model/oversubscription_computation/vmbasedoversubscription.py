from model.slicevmwrapper import SliceVmWrapper
import numpy as np
import math

# Abstract class
class VmBasedOversubscriptionComputation(object):

    def set_context(self, object_wrapper_list : list):
        self.object_wrapper_list = object_wrapper_list

    def compute_sum_cpu_tiers_generic(self, cpu_computation):
        slice_cpu_tier0, slice_cpu_tier1 = 0, 0
        for vmwrapper in self.object_wrapper_list:
            wp_cpu_min, wp_cpu_max = cpu_computation(vmwrapper)
            self.update_cpu_tiers(vmwrapper, wp_cpu_min, wp_cpu_max)
            slice_cpu_tier0 += wp_cpu_min
            slice_cpu_tier1 += wp_cpu_max
        print(slice_cpu_tier0)
        return slice_cpu_tier0, slice_cpu_tier1

    def compute_sum_mem_tiers_generic(self):
        slice_mem_tier0, slice_mem_tier1 = 0, 0
        for vmwrapper in self.object_wrapper_list:
            wp_mem_min, wp_mem_max = (vmwrapper)
            self.update_mem_tiers(vmwrapper, wp_mem_min, wp_mem_max)
            slice_mem_tier0 += wp_mem_min
            slice_mem_tier1 += wp_mem_max
        return slice_mem_tier0, slice_mem_tier1

    def update_cpu_tiers(self, vmwrapper : SliceVmWrapper, cpu_tier0 : int, cpu_tier1 : int):
        studied_slice = vmwrapper.get_last_slice()
        if studied_slice != None:
            studied_slice.update_cpu_tiers(cpu_tier0, cpu_tier1)
        return cpu_tier0, cpu_tier1

    def update_mem_tiers(self, vmwrapper : SliceVmWrapper, mem_tier0 : int, mem_tier1 : int):
        studied_slice = vmwrapper.get_last_slice()
        if studied_slice != None:
            studied_slice.update_mem_tiers(mem_tier0, mem_tier1)
        return mem_tier0, mem_tier1

class RClikeOversubscriptionComputation(VmBasedOversubscriptionComputation):

    def __init__(self, cpu_percentile : int, mem_percentile : int):
        self.cpu_percentile = cpu_percentile
        self.mem_percentile = mem_percentile

    def compute_cpu_tiers_vm(self, vmwrapper : SliceVmWrapper):
        values = vmwrapper.get_slices_raw_metric('cpu_usage')
        generic_tier0 = 0
        if (not vmwrapper.is_vm_ended()) and values: # In dump file, non yet deployed VM are marked with empty values
            config = vmwrapper.get_last_slice().get_cpu_config()
            if vmwrapper.is_historical_full():
                generic_tier0 = np.percentile(values, self.cpu_percentile)*config # convert percent to cores
            else: # not enough value, we use config
                generic_tier0 = config
        return generic_tier0, generic_tier0

    def compute_mem_tiers_vm(self, vmwrapper : SliceVmWrapper):
        values = vmwrapper.get_slices_raw_metric('mem_usage')
        generic_tier0 = 0
        if (not vmwrapper.is_vm_ended()) and values: # In dump file, non yet deployed VM are marked with empty values
            if vmwrapper.is_historical_full():
                generic_tier0 = np.percentile(values, self.mem_percentile)
            else: # not enough value, we use config
                generic_tier0 = vmwrapper.get_last_slice().get_mem_config()
        return generic_tier0, generic_tier0

    def compute_cpu_tiers(self):
        return self.compute_sum_cpu_tiers_generic(self.compute_cpu_tiers_vm)

    def compute_mem_tiers(self):
        return self.compute_sum_cpu_tiers_generic(self.compute_mem_tiers_vm)