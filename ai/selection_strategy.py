'''
Created on Jan 8, 2015

@author: ckomurlu
'''

import numpy as np

class RandomStrategy(object):
    def __init__(self, seed=1):
        self.rgen = np.random.RandomState(seed)
    
    def choices(self, pool, k):
        permuted_pool = self.rgen.permutation(pool)
        permuted_pool = map(tuple, permuted_pool)
        return permuted_pool[:k],permuted_pool[k:]

class UNCSampling(object):
    '''
    This class performs uncertainty sampling based on the model.
    '''
    
    def choices_old(self, model, X, pool, k):
        y_decision = model.decision_function(X[pool])
        uncerts = np.argsort(np.min(np.absolute(y_decision),axis=1))[:k]
        return pool[uncerts]
    
    def choices(self, model, X, pool, k):
        reordered = list()
        reordered.append(tuple([i[0] for i in pool]))
        reordered.append(tuple([i[1] for i in pool]))
        predicted_probs = model.predict_proba(X)
        uncerts = np.argsort(np.max(predicted_probs[reordered],axis=1))[:k]
        selectees = [pool[x] for x in uncerts]
        reducedpool = list()
        for i in range(len(pool)):
            if i not in uncerts:
                reducedpool.append(pool[i])
        return selectees,reducedpool
    
    def choices_model_per_sensor(self, model_dict, X_dict, pool_dict, k):
#       for implementation purpose only,
        model_dict = dict()
        X_dict = dict()
        pool_dict = dict()
        
        current_sensor_list = model_dict.keys()
        for sensor in current_sensor_list:
            pass
        
    