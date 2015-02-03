'''
Created on Jan 19, 2015

@author: ckomurlu
'''

from utils.readdata import convert_time_window_df_randomvar
from joint.iterative_classifier import ICAModel

import numpy as np

def main():
    neighborhood_def = itself_current_only
    train_set,test_set = convert_time_window_df_randomvar(False,
                                                          neighborhood_def)
    use_local_features=True
    use_current_time=True
    is_relat_feature_binary=False
    local_classifier_name = 'svm'
    relat_classifier_name = 'svm'
    print 'immediate update\t', 'No'
    print 'use local feature\t', 'Yes' if use_local_features else 'No'
    print 'previous time/current time\t', 'C' if use_current_time else 'P'
    print 'relative features\t', 'binary' if is_relat_feature_binary else 'ordinal' 
#     C_values = [1000, 10000]
    C_values = [0.01, 0.02, 0.05, 0.1, 1, 10, 100, 1000, 10000]
    for C in C_values:
        icaModel = ICAModel(local_classifier_name=local_classifier_name,
                            relat_classifier_name=relat_classifier_name,
                            use_local_features=use_local_features,
                            use_current_time=use_current_time,
                            relat_classifier_C=C,
                            is_relat_feature_binary=is_relat_feature_binary)
        icaModel.fit(train_set)
#         Y_pred = icaModel.predict(test_set, maxiter=10)
#     Y_pred = icaModel.predict_by_local_classifiers(train_set)
        Y_pred = icaModel.predict_with_neighbors_true_labels_current_time(
                                                        train_set)
        train_acc = icaModel.compute_accuracy(train_set, Y_pred)
        Y_pred = icaModel.predict_with_neighbors_true_labels_current_time(
                                                        test_set)
#         Y_pred = icaModel.predict_by_local_classifiers(test_set)
        test_acc = icaModel.compute_accuracy(test_set, Y_pred)
        print C,'\t', train_acc,'\t',test_acc
#     print icaModel.compute_confusion_matrix(test_set[:,1:], Y_pred[:,1:])

#neighborhood function list
def independent_back(self_id, sensor_IDs):
    neighbors = [(self_id,-1)]
#     neighbors = []
#     neighbors += zip(np.setdiff1d(sensor_IDs, [self_id]),[-1]*
#                     (len(sensor_IDs)-1))
    return neighbors

def all_nodes_current_time(self_id, sensor_IDs):
    neighbors = []
    neighbors += zip(sensor_IDs,[0]*len(sensor_IDs))
    return neighbors

def all_others_current_time(self_id, sensor_IDs):
    neighbors = []
    neighbors += zip(np.setdiff1d(sensor_IDs, [self_id]),[0]*
                    (len(sensor_IDs)-1))
    return neighbors

def itself_current_others_previous(self_id, sensor_IDs):
    neighbors = [(self_id,-1)]
    neighbors += zip(np.setdiff1d(sensor_IDs, [self_id]),[0]*
                    (len(sensor_IDs)-1))
    return neighbors

def itself_current_only(self_id, sensor_IDs):
    neighbors = [(self_id,0)]
#     neighbors += zip(np.setdiff1d(sensor_IDs, [self_id]),[0]*
#                     (len(sensor_IDs)-1))
    return neighbors    

main()