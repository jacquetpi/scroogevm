import pandas as pd
from pandas import concat
from sklearn.metrics import mean_absolute_error
from numpy import asarray
from sklearn.ensemble import RandomForestRegressor
from matplotlib import pyplot
import numpy as np
import matplotlib.pyplot as plt
from gmr.utils import check_random_state
from gmr import MVN, GMM, plot_error_ellipses

class StabilityAssesserGmr(object):

    def get_formatted_time_and_data(self, slicedata : dict, metric : str):
        time = [int(x - slicedata["time"][0]) for x in slicedata["time"]]
        metrics = slicedata[metric]
        return time, metrics

    def get_formatted_nparray_from_list(self, traindata : list, metric : str):
        formatted_time = list()
        formatted_metrics = list()
        for slicedata in traindata:
            time, metrics = self.get_formatted_time_and_data(slicedata, metric)
            formatted_time.extend(time)
            formatted_metrics.extend(metrics)
        # time, metrics = self.get_formatted_time_and_data(traindata[-1], metric)
        # formatted_time.extend(time)
        # formatted_metrics.extend(metrics)
        return np.array([formatted_time, formatted_metrics]).transpose()

    def get_formatted_nparray_from_dict(self, data : dict, metric : str):
        time, metrics = self.get_formatted_time_and_data(data, metric)
        return np.array([time, metrics]).transpose()

    def assess(self, traindata : list, targetdata : dict, metric : str):

        X = self.get_formatted_nparray_from_list(traindata, metric)
        X_test = self.get_formatted_nparray_from_dict(targetdata, metric)
        targettime, target_values = self.get_formatted_time_and_data(targetdata,metric)

        random_state = check_random_state(0) # for reproductibility
        plt.figure(figsize=(10, 5))
        
        X = self.get_formatted_nparray_from_list(traindata, metric)
        X_test = self.get_formatted_nparray_from_dict(targetdata, metric)

        gmm = GMM(n_components=20, random_state=0)
        gmm.from_samples(X)
        targettime = np.array(targettime)[..., np.newaxis]
        Y = gmm.predict(np.array([0]), targettime)
        plt.title("GMR")
        plt.scatter(X[:, 0], X[:, 1])
        plot_error_ellipses(plt.gca(), gmm, colors=["r", "g", "b"])
        plt.plot(X_test, Y, c="k", lw=2)
        plt.plot(targettime, target_values, c="r")

        sum_error = 0
        for i in range(len(targettime)):
            sum_error+= np.abs(Y[i][0] - target_values[i])
        avg_error = round(sum_error/len(targettime),1)
        print("Avg error : ", avg_error)

        plt.show()