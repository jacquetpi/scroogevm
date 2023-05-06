import numpy as np
import pandas as pd
from model.sliceobject import SliceObject
from model.sliceobject import SliceObject

class StabilityAssesserPercentileThreshold(object):

    instance_count = 1  # Static

    def __init__(self):
        self.id = StabilityAssesserPercentileThreshold.instance_count 
        StabilityAssesserPercentileThreshold.instance_count+=1

    def assess(self, old_data : list, new_data : list, threshold_inf : int = 0.9, threshold_sup : int = 1.1, percentile : int = 90):
        applied_threshold_inf = np.percentile(old_data, percentile)*threshold_inf
        applied_threshold_sup =np.percentile(old_data, percentile)*threshold_sup
        return (applied_threshold_inf < np.percentile(new_data, percentile)) and (np.percentile(new_data, percentile) < applied_threshold_sup)

    def is_incoherent_value(self, new_slice : SliceObject, std_metric : str, metric : str = None,  percentile : int = 90, threshold : int = 1):
        
        last_slice = self.get_last_slice()

        last_values = self.get_slices_raw_metric(metric=metric)
        new_values = last_slice.get_raw_metric(metric=metric)

        return self.assess(old_data=last_values, new_data=new_values, threshold=threshold, percentile=percentile)

    def compute_cpu_state_of_new_slice(self, new_slice : SliceObject):
        current_cpu_state = self.get_last_slice().get_cpu_state()
        # If config changed
        if (self.get_last_slice().get_cpu_config() != new_slice.cpu_config):
            self.debug_cpu_reason = ">0 conf changed"
            return 0
        # If oc is too important
        if self.is_incoherent_value(new_slice=new_slice, metric='oc_sched_wait', std_metric='oc_sched_wait_std'):
            self.debug_cpu_reason = ">0 perf oc desc"
            return 0
        # If behavior changed
        if self.is_incoherent_value(new_slice=new_slice, metric='cpu_avg', std_metric='cpu_std'):
            self.debug_cpu_reason = "-1 avg increase"
            return current_cpu_state-1
        if self.is_incoherent_value(new_slice=new_slice, cpu_percentile=self.cpu_percentile, std_metric='cpu_std'):
            self.debug_cpu_reason = "-1 nth increase"
            return current_cpu_state-1
        # Stability case
        self.debug_cpu_reason = "+1 usage stable"
        return current_cpu_state+1

    def compute_mem_state_of_new_slice(self, new_slice : SliceObject):
        current_mem_state = self.get_last_slice().get_mem_state()
        # If config changed
        if (self.get_last_slice().get_mem_config() != new_slice.mem_config):
            self.debug_mem_reason = ">0 conf changed"
            return 0
        # If oc is too important
        if self.is_incoherent_value(new_slice=new_slice, metric='oc_page_fault', std_metric='oc_page_fault_std'):
            self.debug_mem_reason = ">0 perf oc desc"
            return 0
        # If behavior changed
        if self.is_incoherent_value(new_slice=new_slice, metric='mem_avg', std_metric='mem_std'):
            self.debug_mem_reason = "-1 avg increase"
            return current_mem_state-1
        if self.is_incoherent_value(new_slice=new_slice, mem_percentile=self.mem_percentile, std_metric='mem_std'):
            self.debug_mem_reason = "-1 nth increase"
            return current_mem_state-1
        # Stability case
        self.debug_mem_reason = "+1 usage stable"
        return current_mem_state+1

    def compute_state_of_new_slice(self, new_slice : SliceObject):
        cpu_state = 0
        mem_state = 0
        if(self.is_historical_full()):
            cpu_state = self.compute_cpu_state_of_new_slice(new_slice)
            mem_state = self.compute_mem_state_of_new_slice(new_slice)
        new_slice.update_state(cpu_state = cpu_state, mem_state = mem_state)