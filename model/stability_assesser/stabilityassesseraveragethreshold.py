import numpy as np

class StabilityAssesserAverageThreshold(object):

    instance_count = 1  # Static

    def __init__(self):
        self.id = StabilityAssesserAverageThreshold.instance_count
        StabilityAssesserAverageThreshold.instance_count+=1

    def assess(self, old_data : list, new_data : list, threshold : int = 1):
        applied_threshold = np.average(old_data) + threshold * np.std(old_data)
        return np.average(new_data) < applied_threshold