from model.sliceobjectwrapper import SliceObjectWrapper
import numpy as np
import math

# Abstract class
class NodeBasedOversubscriptionComputation(object):

    def set_context(self, object_wrapper : SliceObjectWrapper):
        self.object_wrapper = object_wrapper 

    def update_cpu_tiers(self, cpu_tier0 : int, cpu_tier1 : int):
        studied_slice = self.object_wrapper.get_last_slice()
        studied_slice.update_cpu_tiers(cpu_tier0, cpu_tier1)
        return cpu_tier0, cpu_tier1

    def update_mem_tiers(self, mem_tier0 : int, mem_tier1 : int):
        studied_slice = self.object_wrapper.get_last_slice()
        studied_slice.update_mem_tiers(mem_tier0, mem_tier1)
        return mem_tier0, mem_tier1

    # Misc functions
    def round_to_upper_nearest(self, x : int, nearest_val : int):
        return nearest_val * math.ceil(x/nearest_val)

class DoaOversubscriptionComputation(NodeBasedOversubscriptionComputation):

    def __init__(self):
        self.increase_ratio = 20 # increase by 5%
        self.treshold = 0.95
        self.decrease_ratio = 2 # decrease by 20%
        self.max_ratio = 3 # Due to implementation, max OC is not bounded in a non "scheduler linked" env

    def __compute_generic_tiers(self, value : str, previous_tier0 : int, config_resources : int):
        applied_threshold = config_resources*self.treshold
        if value < applied_threshold:
            # To increase oversubscribtion value, we diminue the "seen as used" quantity
            generic_tier0 = previous_tier0 - round(config_resources/self.increase_ratio)
            min_value = (-(self.max_ratio-1)*config_resources) # negative, min used value of ratio 2 for a 256 core config is -256
            if generic_tier0 < min_value: # 
                generic_tier0 = min_value
        else:
            # To decrease oversubscribtion value, we increase the "seen as used" quantity
            generic_tier0 =  previous_tier0 + round(config_resources/self.decrease_ratio)
        
        return generic_tier0, generic_tier0 # Debug0 No Tier1 in this paper

    def compute_cpu_tiers(self):
        studied_slice = self.object_wrapper.get_last_slice()
        previous_slice = self.object_wrapper.get_nth_to_last_slice(1)
        if previous_slice is None :
            init_value = studied_slice.get_booked_cpu() # Init at 1:1
            previous_cpu_tier0, previous_cpu_tier1 = (init_value, init_value)
        else:
            previous_cpu_tier0, previous_cpu_tier1 = previous_slice.get_cpu_tiers()
        cpu_config = studied_slice.get_cpu_config()
        max_value = studied_slice.get_cpu_max()
        cpu_tier0, cpu_tier1 = self.__compute_generic_tiers(value=max_value,previous_tier0=previous_cpu_tier0,config_resources=cpu_config)
        return super().update_cpu_tiers(cpu_tier0, cpu_tier1)

    def compute_mem_tiers(self):
        studied_slice = self.object_wrapper.get_last_slice()
        previous_slice = self.object_wrapper.get_nth_to_last_slice(1)
        if previous_slice is None :
            init_value = studied_slice.get_booked_mem()# Init at 1:1
            previous_mem_tier0, previous_mem_tier1 = (init_value, init_value)
        else:
            previous_mem_tier0, previous_mem_tier1 = previous_slice.get_mem_tiers()
        mem_config = studied_slice.get_mem_config()
        max_value = studied_slice.get_mem_max()
        cpu_tier0, cpu_tier1 = self.__compute_generic_tiers(value=max_value,previous_tier0=previous_mem_tier0,config_resources=mem_config)
        return super().update_mem_tiers(cpu_tier0, cpu_tier1)

class PercentileOversubscriptionComputation(NodeBasedOversubscriptionComputation):

    def __init__(self, cpu_percentile : int, mem_percentile : int):
        self.cpu_percentile = cpu_percentile
        self.mem_percentile = mem_percentile

    def __compute_generic_tiers(self, metric : str, percentile : int):
        values = self.object_wrapper.get_slices_raw_metric(metric)
        generic_tier0 = np.percentile(values, percentile)
        return generic_tier0, generic_tier0 # No Tier1 in this paper

    def compute_cpu_tiers(self):
        cpu_tier0, cpu_tier1 = self.__compute_generic_tiers(metric='cpu_usage', percentile=self.cpu_percentile)
        return super().update_cpu_tiers(cpu_tier0, cpu_tier1)

    def compute_mem_tiers(self):
        mem_tier0, mem_tier1 = self.__compute_generic_tiers(metric='mem_usage', percentile=self.mem_percentile)
        return super().update_mem_tiers(mem_tier0, mem_tier1)

class GreedyOversubscriptionComputation(NodeBasedOversubscriptionComputation):

    def __init__(self):
        self.bound_min  = 2.0
        self.bound_max  = 5.0
        self.ratio_init = self.bound_min  + (self.bound_max-self.bound_min)/2

        self.ratio_inc = 0.2
        self.ratio_dec = 0.1

    def __compute_ratio(self, current_ratio: int, quiescient : bool, increase : bool):
        # Compute value
        if quiescient:
            current_ratio -= self.ratio_dec
        else:
            if increase: current_ratio += self.ratio_inc # let as it is if unstable on a decreasing trend
        # Manage bounds
        if current_ratio>self.bound_max: current_ratio=self.bound_max
        if current_ratio<self.bound_min: current_ratio=self.bound_min
        return current_ratio

    def __compute_generic_tiers(self, current_avg : int, current_std : int, current_ratio : int):

        generic_tier0 = current_avg + current_ratio*current_std

        print("Greedy: ", generic_tier0, "from avg", current_avg, ", using ratio", current_ratio)

        generic_tier1 = generic_tier0 # No Tier1 in this paper
        return generic_tier0, generic_tier1
        
    # CPU tiers as threshold
    def compute_cpu_tiers(self):

        # Retrieve current context
        current_slice = self.object_wrapper.get_last_slice()
        cpu_traces = self.object_wrapper.get_slices_raw_metric('cpu_usage')
        current_avg = np.average(cpu_traces)
        current_std = np.std(cpu_traces)
        is_stable = current_slice.is_cpu_stable()
        
        # Retrieve last slice intel
        previous_slice = self.object_wrapper.get_nth_to_last_slice(1)
        previous_avg = None
        cpu_ratio = self.ratio_init
        if previous_slice is not None :
            previous_avg = self.round_to_upper_nearest(previous_slice.get_cpu_avg(), nearest_val=0.1)
            cpu_ratio = getattr(previous_slice, 'cpu_ratio')
        
        # Compute ratio
        # delta_provision = booked_resources - previous_booked if previous_booked != None else booked_resources
        delta_usage = current_avg - previous_avg  if previous_avg != None else 0
        cpu_ratio = self.__compute_ratio(cpu_ratio, is_stable, delta_usage>0)

        # Compute tiers
        cpu_tier0, cpu_tier1 = self.__compute_generic_tiers(current_avg=current_avg, current_std=current_std, current_ratio=cpu_ratio)

        # Update ratio
        setattr(current_slice, 'cpu_ratio', cpu_ratio)
        return super().update_cpu_tiers(cpu_tier0, cpu_tier1)

    # Mem tiers as threshold
    def compute_mem_tiers(self):

        # Retrieve current context
        current_slice = self.object_wrapper.get_last_slice()
        mem_traces = self.object_wrapper.get_slices_raw_metric('mem_usage')
        current_avg = np.average(mem_traces)
        current_std = np.std(mem_traces)
        is_stable = current_slice.is_mem_stable()

        # Retrieve last slice intel
        previous_slice = self.object_wrapper.get_nth_to_last_slice(1)
        previous_avg = None
        mem_ratio = self.ratio_init
        if previous_slice is not None :
            previous_avg = self.round_to_upper_nearest(previous_slice.get_mem_avg(), nearest_val=0.1)
            mem_ratio = getattr(previous_slice, 'mem_ratio')

        # Compute ratio
        # delta_provision = booked_resources - previous_booked if previous_booked != None else booked_resources
        delta_usage = current_avg - previous_avg  if previous_avg != None else 0
        mem_ratio = self.__compute_ratio(mem_ratio, is_stable, delta_usage>0)
        
        # Compute tiers
        mem_tier0, mem_tier1 = self.__compute_generic_tiers(current_avg=current_avg, current_std=current_std, current_ratio=mem_ratio)

        # Update ratio
        setattr(current_slice, 'mem_ratio', mem_ratio)
        return super().update_mem_tiers(mem_tier0, mem_tier1)

class NSigmaOversubscriptionComputation(NodeBasedOversubscriptionComputation):

    def __init__(self, N : int):
        self.N = 5

    def __compute_generic_tiers(self, metric : str):
        values = self.object_wrapper.get_slices_raw_metric(metric)
        generic_tier0 = np.average(values) + (self.N * np.std(values))
        return generic_tier0, generic_tier0

    def compute_cpu_tiers(self):
        cpu_tier0, cpu_tier1 = self.__compute_generic_tiers(metric='cpu_usage')
        return super().update_cpu_tiers(cpu_tier0, cpu_tier1)

    def compute_mem_tiers(self):
        mem_tier0, mem_tier1 = self.__compute_generic_tiers(metric='mem_usage')
        return super().update_mem_tiers(mem_tier0, mem_tier1)

class BorgDefaultOversubscriptionComputation(NodeBasedOversubscriptionComputation):

    def __init__(self, oversubscription_ratio : int):
        self.oversubscription_ratio = oversubscription_ratio

    def __compute_generic_tiers(self, config_metric : str, booked_metric : str):
        booked = getattr(self.object_wrapper.get_last_slice(), booked_metric)
        generic_tier0 = booked/self.oversubscription_ratio
        return generic_tier0, generic_tier0

    def compute_cpu_tiers(self):
        cpu_tier0, cpu_tier1 = self.__compute_generic_tiers(config_metric='cpu_config', booked_metric='booked_cpu')
        return super().update_cpu_tiers(cpu_tier0, cpu_tier1)

    def compute_mem_tiers(self):
        mem_tier0, mem_tier1 = self.__compute_generic_tiers(config_metric='mem_config', booked_metric='booked_mem')
        return super().update_mem_tiers(mem_tier0, mem_tier1)