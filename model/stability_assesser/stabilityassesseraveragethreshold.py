import numpy as np

class StabilityAssesserAverageThreshold(object):

    instance_count = 1  # Static

    def __init__(self):
        self.id = StabilityAssesserAverageThreshold.instance_count
        StabilityAssesserAverageThreshold.instance_count+=1

    def assess(self, old_data : list, new_data : list, threshold_inf : int = 1, threshold_sup : int = 1):
        applied_threshold_inf = np.average(old_data) - threshold_inf * np.std(old_data)
        applied_threshold_sup = np.average(old_data) + threshold_sup * np.std(old_data)
        return (applied_threshold_inf < np.average(new_data)) and (np.average(new_data) < applied_threshold_sup)