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

    def __init__(self, cpu_percentile : int, mem_percentile : int):
        self.cpu_percentile = cpu_percentile
        self.mem_percentile = mem_percentile

        self.streak_min = 3
        self.streak_max = 10
        self.streak_inc = 1
        self.streak_dec = 2

    def __compute_streak(self, current_streak: int, quiescient : bool, increase : bool):
        # Compute value
        if quiescient:
            current_streak += self.streak_inc
        else:
            if increase: current_streak -= self.streak_dec # let as it is if unstable on a decreasing trend
        # Manage bounds
        if current_streak>self.streak_max: current_streak=self.streak_max
        if current_streak<self.streak_min: current_streak=self.streak_min
        return current_streak

    def __compute_generic_tiers(self, current_percentile : int, booked_resources : int, 
                                    previous_percentile : int, previous_booked : int,
                                    stable_streak : int):
        applied_ratio = self.streak_max - stable_streak + self.streak_min

        generic_tier0 = current_percentile + (256/self.streak_max)

        print("Greedy: ", generic_tier0, "from percentile", generic_tier0, ", using streak", stable_streak, "on applied ratio", applied_ratio, "with delta", (256/applied_ratio))

        generic_tier1 = generic_tier0 # No Tier1 in this paper
        return generic_tier0, generic_tier1
        
    # CPU tiers as threshold
    def compute_cpu_tiers(self):

        # Retrieve current slice intel
        current_slice = self.object_wrapper.get_last_slice()
        current_percentile = self.round_to_upper_nearest(current_slice.get_cpu_percentile(self.cpu_percentile), nearest_val=0.1)
        current_booked_cpu = current_slice.get_booked_cpu()
        is_stable = current_slice.is_cpu_stable()
        
        # Retrieve last slice intel
        previous_slice = self.object_wrapper.get_nth_to_last_slice(1)
        previous_percentile, previous_booked_cpu = (None, None)
        cpu_stable_streak = 0
        if previous_slice is not None :
            previous_percentile = self.round_to_upper_nearest(previous_slice.get_cpu_percentile(self.cpu_percentile), nearest_val=0.1)
            previous_booked_cpu = previous_slice.get_booked_cpu()
            cpu_stable_streak = getattr(previous_slice, 'cpu_stable_streak')
        
        # Compute streak
        # delta_provision = booked_resources - previous_booked if previous_booked != None else booked_resources
        delta_usage = current_percentile - previous_percentile  if previous_percentile != None else 0
        cpu_stable_streak = self.__compute_streak(cpu_stable_streak, is_stable, delta_usage>0)

        # Compute tiers
        cpu_tier0, cpu_tier1 = self.__compute_generic_tiers(current_percentile=current_percentile, booked_resources=current_booked_cpu, 
                                                    previous_percentile=previous_percentile, previous_booked=previous_booked_cpu,
                                                    stable_streak=cpu_stable_streak)

        # Update streak
        setattr(current_slice, 'cpu_stable_streak', cpu_stable_streak)
        return super().update_cpu_tiers(cpu_tier0, cpu_tier1)

    # Mem tiers as threshold
    def compute_mem_tiers(self):
        # Retrieve current slice intel
        return super().update_mem_tiers(0, 0)
        studied_slice = self.object_wrapper.get_last_slice()
        max_percentile = self.round_to_upper_nearest(x=self.object_wrapper.get_slices_max_metric(mem_percentile=self.mem_percentile), nearest_val=1)
        booked_mem = studied_slice.get_booked_mem()
        is_stable = studied_slice.is_mem_stable()
        # Retrieve last slice intel
        previous_slice = self.object_wrapper.get_nth_to_last_slice(1)
        previous_mem_tier0, previous_mem_tier1, previous_mem_booked = (None, None, None)
        if previous_slice is not None :
            previous_mem_tier0, previous_mem_tier1 = previous_slice.get_mem_tiers()
            previous_mem_booked = previous_slice.get_booked_mem()
        # Compute tiers
        mem_tier0, mem_tier1 = self.__compute_generic_tiers(is_stable=is_stable, max_percentile=max_percentile, booked_resources=booked_mem, 
                                                    previous_tier0=previous_mem_tier0, previous_tier1=previous_mem_tier1, previous_booked=previous_mem_booked)
        return super().update_mem_tiers(mem_tier0, mem_tier1)

class NSigmaOversubscriptionComputation(NodeBasedOversubscriptionComputation):

    def __init__(self, N : int):
        self.N = N

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