'''
Created on May 12, 2015

@author: ckomurlu
'''
from models.ml_reg_model import MLRegModel
from utils.node import Neighborhood
from utils.metropolis_hastings import MetropolisHastings
from utils import readdata
import utils.properties
from utils.readdata import convert_time_window_df_randomvar_hour
from data.data_provider import DataProvider
import dynamic_linear_gaussian as dlg

import numpy as np
from scipy.stats import norm
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import minimum_spanning_tree
import cPickle as cpk
from collections import Counter
from time import time
import numbers



class GaussianDBN(MLRegModel):
    '''
    classdocs
    '''


    def __init__(self):
        '''
        Constructor
        '''
        self.sortedids = list()
        self.cpdParams = object()
        self.parentDict = dict()
        self.childDict = dict()
        self.rvCount = -1
        self.topology = 'TBD'
        self.means = np.empty(shape=0)

    def fit(self, trainset, topology='original', **kwargs):
        if utils.properties.learningDBN == 'multivariate_Guassian':
            self.fit_by_multivariate_gaussian_distribution(trainset=trainset, topology=topology, **kwargs)
        elif utils.properties.learningDBN == 'lasso_regression':
            self.fit_by_lasso_regression()

    def fit_by_lasso_regression(self):
        if utils.properties.data == 'temperature':
            file_ = open(r'C:\Users\CnrKmrl\Documents\workbench\data\intelResearch\lasso_learned_parameters_IntelTemp[22_34,70_82,118_130].pkl', 'r')
        if utils.properties.data == 'humidity':
            file_ = open(r'C:\Users\CnrKmrl\Documents\workbench\data\intelResearch\lasso_learned_parameters_IntelHumid[22_34,70_82,118_130].pkl', 'r')
        if utils.properties.data == 'wunderground-cwide':
            file_ = open(r'C:\Users\CnrKmrl\Documents\workbench\data\wunderground\countrywide\lasso_learned_parameters_[0_124].pkl', 'r')
        (pruned_parents, initbeta0s, initbetas, initsigmasqs, interbeta0s, interbetas, intersigmasqs) = cpk.load(file_)
        self.rvCount = len(pruned_parents)
        self.sortedids = range(self.rvCount)
        self.parentDict = {k: [tpl[0] if tpl[1] == 0 else tpl[0] + self.rvCount for tpl in v] for k, v in
                           pruned_parents.items()}
        self.cpdParams = np.empty(shape=(self.rvCount, 2), dtype=tuple)
        for var in self.sortedids:
            self.cpdParams[var, 0] = (initbeta0s[var], np.array(initbetas[var])[:, np.newaxis], initsigmasqs[var])
            self.cpdParams[var, 1] = (interbeta0s[var], np.array(interbetas[var])[:, np.newaxis], intersigmasqs[var])
        self.childDict = self.getChildDict()
        self.childDict = {key: filter(lambda x: x<self.rvCount, self.childDict[key]) for key in self.childDict}


    def fit_by_multivariate_gaussian_distribution(self, trainset, topology='original', **kwargs):
        '''
        Parameters
        trainset: It has to be a 2D matrix. Each entry should be a rv object,
            rows are sensors, columns are time
        topology: 3 network topologies can be selected. 'original' is the way it is
            computed based on only information matrix.  'mst' is the it is computed
            using maximum spanning tree over information matrix. 'mst enriched' is 
            the way one more connection is added to all nodes that have only one
            parent
        '''
        self.rvCount = trainset.shape[0]
        X = np.vectorize(lambda x: x.true_label)(trainset)
        self.means = np.mean(X, axis=1)
        self.means1 = np.mean(X[:, :-1], axis=1)
        self.means2 = np.mean(X[:, 1:], axis=1)
        mea100 = np.append(self.means1, self.means2)
        cova = np.cov(X[:, :])
        Y = np.append(X[:, 1:], X[:, :-1], axis=0)
        cova100 = np.cov(Y)
        infomat = np.linalg.inv(cova)
        absround = np.absolute(np.around(infomat, 6))
        self.topology = topology
        if topology == 'imt':
            self.setParentsByThreshold(absround)
        elif topology == 'mst':
            self.setParentsByMST(absround)
        elif topology == 'mst_enriched':
            self.setParentsByMST_enriched(absround)
        elif topology == 'k2_bin10' or topology == 'k2_bin5':
            topology_file_path = DataProvider.get_topology_file_path()
            self.setParentsByK2(topology_file_path)
        elif topology == 'fully_connected':
            self.set_parents_fully_connected()
        elif topology == 'lasso':
            raise ValueError('topology is set as lasso, but topology learning is multivariate Gaussian learning.')
        else:
            raise ValueError('topology should be either imt, or mst or mst_enriched.')
        self.cpdParams = np.empty(shape=self.means.shape + (2,), dtype=tuple)
        for i in self.sortedids:
            self.cpdParams[i, 0] = self.__computeCondGauss(i,self.parentDict,mea100,
                                                        cova100,initial=True)
            self.cpdParams[i, 1] = self.__computeCondGauss(i,self.parentDict,
                                                        mea100,cova100)

    def set_parents_fully_connected(self):
        self.sortedids = range(self.rvCount)
        self.parentDict = {id_: range(id_) + [id_ + self.rvCount] for id_ in self.sortedids}
        self.childDict = {id_: range(id_+1, self.rvCount) for id_ in self.sortedids}

    def setParentsByMST(self,absround):
        self.parentDict = dict()
        for i in range(self.rvCount):
            self.parentDict[i] = list()
        Tabsround = minimum_spanning_tree(csr_matrix(-absround))
        Tabscoo = Tabsround.tocoo()
        connectionConcat = np.append(Tabscoo.col,Tabscoo.row)
        connectionCounts = Counter(connectionConcat)
        startidx = np.argmax(connectionCounts.values())
        grey = [startidx]
        black = list()
        colList = Tabscoo.col
        rowList = Tabscoo.row
        while grey:
            cur = grey.pop(0)
            black.append(cur)
            indicesInCol = np.where(np.array(colList) == cur)
            children = rowList[indicesInCol[0]]
            rowList = np.delete(rowList,indicesInCol[0])
            colList = np.delete(colList,indicesInCol[0])
            for child in children:
                self.parentDict[child].append(cur)
            grey += children.tolist()

            indicesInRow = np.where(np.array(rowList) == cur)
            children = colList[indicesInRow[0]]
            rowList = np.delete(rowList,indicesInRow[0])
            colList = np.delete(colList,indicesInRow[0])
            for child in children:
                self.parentDict[child].append(cur)
            grey += children.tolist()
        for key in self.parentDict:
            self.parentDict[key].append(key + self.rvCount)
        self.sortedids = black
        self.childDict = self.getChildDict()


    def setParentsByMST_enriched(self, absround):
        raise NotImplementedError('This topology has implementation problems.')
        self.parentDict = dict()
        for i in range(self.rvCount):
            self.parentDict[i] = list()
        trilIndices = np.tril_indices(self.rvCount)
        absround[trilIndices] = 0
        mstSparse = minimum_spanning_tree(csr_matrix(-absround))
        mstEdges = (mstSparse.toarray() != 0)
        connectCounts = np.sum(mstEdges,axis=0) + np.sum(mstEdges,axis=1)
        startidx = np.argmax(connectCounts)
        colList = mstSparse.tocoo().col
        rowList = mstSparse.tocoo().row
        for i in np.where(connectCounts == 1)[0]:
            sortedInd = np.argsort(absround[i])
            for j in range(-1,-self.rvCount,-1):
#                 if (not sortedInd[j] in self.parentDict[i]) and \
#                     (not i in self.parentDict[sortedInd[j]]):
                if not mstEdges[i,sortedInd[j]] and \
                    not mstEdges[sortedInd[j],i]:
                    if i < sortedInd[j]:
                        mstEdges[i,sortedInd[j]] = True
                    else:
                        mstEdges[sortedInd[j],i] = True
                    colList = np.hstack((colList,[i]))
                    rowList = np.hstack((rowList,[sortedInd[j]]))
#                     rowList.append(sortedInd[j])
#                     self.parentDict[i].append(sortedInd[j])
                    break
        grey = set([startidx])
        black = list()
        while grey:
            cur = grey.pop()
            black.append(cur)
            indicesInCol = np.where(np.array(colList) == cur)
            children = rowList[indicesInCol[0]]
            rowList = np.delete(rowList,indicesInCol[0])
            colList = np.delete(colList,indicesInCol[0])
            for child in children:
                self.parentDict[child].append(cur)
            grey |= set(children.tolist())
            indicesInRow = np.where(np.array(rowList) == cur)
            children = colList[indicesInRow[0]]
            rowList = np.delete(rowList,indicesInRow[0])
            colList = np.delete(colList,indicesInRow[0])
            for child in children:
                self.parentDict[child].append(cur)
            grey |= set(children.tolist())
        self.sortedids = black
        for key in self.parentDict:
            self.parentDict[key].append(key + self.rvCount)

    def setParentsByThreshold(self, absround):
        (a,b) = np.nonzero(absround > 24.3)
        condict = dict()
        for i in range(a.shape[0]):
            if a[i] not in condict:
                condict[a[i]] = list()
            condict[a[i]].append(b[i])
        concount = np.empty((len(condict),),dtype=np.int_)
        for key in condict:
            if key in condict[key]:
                condict[key].remove(key)
            concount[key] = len(condict[key])
        self.sortedids = np.argsort(concount)[::-1].astype(np.int8).tolist()
        arclist = list()
        for id_ in self.sortedids:
            for nei in condict[id_]:
                if self.sortedids.index(id_) < self.sortedids.index(nei):
                    arclist.append((id_,nei))
        self.parentDict = self.__convertArcsToGraphInv(arclist)
        self.checkParentChildOrder()
        for currentid in self.sortedids:
            try:
                self.parentDict[currentid].append(currentid + 50)
            except KeyError:
                self.parentDict[currentid] = list()
                self.parentDict[currentid].append(currentid + 50)

    def setParentsByK2(self, topology_file_path):
        self.sortedids = range(self.rvCount)
        (self.parentDict,self.childDict) = cpk.load(open(topology_file_path,'rb'))
        for key in self.parentDict:
            self.parentDict[key].append(key + self.rvCount)


    def setParentsByK2_backup(self, binCount):
        self.sortedids = range(self.rvCount)
        if 10 == binCount:
            (self.parentDict,self.childDict) = cpk.load(
                open(utils.properties.k2bin10StructureParentChildDictPath,'rb'))
        elif 5 == binCount:
            (self.parentDict,self.childDict) = cpk.load(
                open(utils.properties.k2bin5StructureParentChildDictPath,'rb'))
        else:
            raise ValueError('Bin count can only be selected as 10 or 5.' + str(binCount) + ' was given.')
        for key in self.parentDict:
            self.parentDict[key].append(key + self.rvCount)


    def __convertArcsToGraphInv(self,arclist):
        graph = dict()
        for edge in arclist:
            if edge[1] not in graph:
                graph[edge[1]] = list()
            graph[edge[1]].append(edge[0])
        return graph

    def __computeCondGauss_bkp(self, sensid, parentDict, mea, cova, initial=False):
#     try:
#         parents = parentDict[sensid]
#     except KeyError:
#         return mea[sensid],0,cova[sensid,sensid]
        parents = parentDict[sensid]
        if initial == True:
            parents = parents[:-1]
            if parents == []:
                return mea[sensid],0,cova[sensid,sensid]
        firstInd = np.tile(tuple(parents),len(parents))
        secondInd = np.repeat(tuple(parents),len(parents))
        YY = cova[sensid,sensid]
        YX = cova[sensid,tuple(parents)]
        XY = cova[tuple(parents),sensid]
        XXinv = np.linalg.inv(cova[firstInd,secondInd].reshape(len(parents),
                                                               len(parents)))
        b0 = mea[sensid] - np.dot(np.dot(YX, XXinv), mea[list(parents)])
        b = np.dot(XXinv,YX)
        sigsq = YY - np.dot(np.dot(YX,XXinv),XY.reshape(-1,1))
        return b0,b,sigsq[0]

    def __computeCondGauss(self, sensid, parentDict, mea, cova, initial=False):
#     try:
#         parents = parentDict[sensid]
#     except KeyError:
#         return mea[sensid],0,cova[sensid,sensid]
        parents = parentDict[sensid]
        if initial == True:
            parents = parents[:-1]
            if parents == []:
                return mea[sensid],np.array([]),cova[sensid,sensid]
        firstInd = np.tile(tuple(parents),len(parents))
        secondInd = np.repeat(tuple(parents),len(parents))
        YY = cova[sensid,sensid].reshape(1,1)
        YX = cova[sensid,tuple(parents)].reshape(1,-1)
        XY = cova[tuple(parents),sensid].reshape(-1,1)
        XXinv = np.linalg.inv(cova[firstInd,secondInd].reshape(len(parents),
                                                               len(parents)))
        b0 = mea[sensid].reshape(1,1) - np.dot(np.dot(YX, XXinv),
                                            mea[list(parents)].reshape(-1,1))
        b = np.dot(XXinv,XY)
        sigsq = YY - np.dot(np.dot(YX,XXinv),XY.reshape(-1,1))
        return b0,b,sigsq[0]

    def likelihoodWeighting(self, evidMap, testset, sampleSize=100):
        if not evidMap.shape[0] == len(self.sortedids):
            raise ValueError('Evidence map doesn\'t have appropriate dimension for sensors')
        numSlice = evidMap.shape[1]
        sampleStorage = np.empty(shape = (sampleSize,len(self.sortedids),numSlice),
                                 dtype=np.float64)
        weightList = list()
        logWeightList = list()
        for currentSample in xrange(sampleSize):
#             print currentSample,
            sampleWeight = 1
            logSampleWeight = 0
            for currentid in self.sortedids:
                (b0,b,var) = self.cpdParams[currentid,0]
                parents = self.parentDict[currentid][:-1]
                if parents == []:
                    currentmean = b0
                else:
                    parentValues = sampleStorage[currentSample,parents,0]
                    currentmean = b0 + np.dot(b.T,parentValues.reshape(-1,1))
                if evidMap[currentid,0]:
                    sampleStorage[currentSample,currentid,0] = \
                        testset[currentid,0].true_label
                    rv = norm(loc=currentmean,scale=var**.5)
                    if parents != []:
                        currentCoef = rv.pdf(sampleStorage[currentSample,currentid,0])
#                         print currentCoef
                        sampleWeight *= currentCoef.reshape(-1)
                        logSampleWeight += np.log(currentCoef.reshape(-1))
                else:
                    sampleStorage[currentSample,currentid,0] = \
                        np.random.normal(currentmean,var**.5)
            for t in xrange(1,numSlice):
        #         print '\t',t
                for currentid in self.sortedids:
        #             print '\t\t',currentid
                    parents = self.parentDict[currentid]
                    (b0,b,var) = self.cpdParams[currentid,1]
                    parentValuesT = sampleStorage[currentSample,parents[:-1],t]
                    itselfPrevious = sampleStorage[currentSample,currentid,t-1]
                    parentValues = np.append(parentValuesT, itselfPrevious)
                    currentmean = b0 + np.dot(b.T,parentValues.reshape(-1,1))
                    if evidMap[currentid,t]:
                        sampleStorage[currentSample,currentid,t] = \
                            testset[currentid,t].true_label
                        rv = norm(loc=currentmean,scale=var**.5)
                        currentCoef = rv.pdf(sampleStorage[currentSample,currentid,t])
#                         print currentCoef
                        sampleWeight *= currentCoef.reshape(-1)
                        logSampleWeight += np.log(currentCoef.reshape(-1))
                    else:
                        sampleStorage[currentSample,currentid,t] = \
                            np.random.normal(currentmean,var**.5)
#             print np.exp(sampleWeight)
            weightList.append(sampleWeight)
            logWeightList.append(np.exp(logSampleWeight))
#             print sampleWeight
#         print weightList
        return (sampleStorage, weightList, logWeightList)

    def predictViaMH(self, testMat, evidMat, tWin, sampleSize=2000, burnInCount=1000, samplingPeriod=2, startupVals=None,
                obsrate=0.0, trial=0, t=0, **kwargs):
        if t < tWin:
            testset = testMat[:, :t+1]
            curEvidMat = evidMat[:, :t+1]
        else:
            testset = testMat[:, t+1-tWin:t+1]
            curEvidMat = evidMat[:, t+1-tWin:t+1]
        T = evidMat.shape[1]
        if startupVals is None:
            # startupVals = np.ones((self.rvCount,T),dtype=np.float_)*20
            startupVals = np.repeat(self.means.reshape(-1, 1), T, axis=1)
        else:
            assert testset.shape==startupVals.shape, 'testset and startupVals shapes don\'t match'
        ytest = np.vectorize(lambda x: x.true_label)(testset)
#         width = [0.4,0.3,0.3,0.4,0.2,0.3,0.2,0.3,0.3,0.8,0.8,1.6,1,0.9,0.4,0.5,0.4,0.5,0.6,0.3,0.4,1.1,
#              0.3,0.3,0.3,0.3,0.3,0.3,0.4,0.8,0.9,0.7,0.9,0.3,0.7,0.7,0.4,0.4,0.6,0.4,1.2,0.5,0.5,1,
#              0.6,1.5,1.4,1.5,0.5,0.5]
        width = utils.properties.mh_startupWidth
        metropolisHastings = MetropolisHastings()
        (data,accList,propVals,accCount,burnInCount, widthMat) = metropolisHastings.sampleTemporal(
            self.sortedids, self.parentDict, self.cpdParams, startupVals, evidMat, ytest,
            sampleSize=sampleSize, burnInCount=burnInCount, samplingPeriod=samplingPeriod,
            proposalDist='uniform', width=width, tuneWindow=utils.properties.mh_tuneWindow)
        # cpk.dump((data,accList,propVals,accCount,burnInCount,widthMat), open(utils.properties.outputDirPath +
        #     str(obsrate) +'/mhResults_topology={}_sampleSize={}_obsrate={}_trial={}_t={}_{}.pkl'.format(
        #     self.topology,sampleSize,obsrate,trial,t,utils.properties.timeStamp),'wb'))
        dataarr = np.array(data)
        muData = np.mean(dataarr[burnInCount::samplingPeriod,:,:],axis=0)
        sigmasqData = np.var(dataarr[burnInCount::samplingPeriod,:,:],axis=0)
        return muData, sigmasqData

    def predict(self, testMat, evidMat, t, last_slice_only=False, **kwargs):
        T = t+1
        assert(testMat.shape[0] == self.rvCount)
        assert(testMat.shape[1] >= T)
        assert(evidMat.shape[0] == self.rvCount)
        assert(evidMat.shape[1] >= T)
        parents = self._convertParents()
        initbeta0s = map(lambda x: x[0], self.cpdParams[:, 0])
        initbetas = map(lambda x: x[1], self.cpdParams[:, 0])
        initsigmasqs = map(lambda x: x[2], self.cpdParams[:, 0])
        interbeta0s = map(lambda x: x[0], self.cpdParams[:, 1])
        interbetas = map(lambda x: x[1], self.cpdParams[:, 1])
        intersigmasqs = map(lambda x: x[2], self.cpdParams[:, 1])
        cova = dlg.computeMultivariateCovarianceMatrixDynamic(parents, initbetas, initsigmasqs, interbetas,
                                                              intersigmasqs, T)
        mu = dlg.computeMultivariateMeanVectorDynamic(parents, initbeta0s, initbetas, interbeta0s, interbetas, T)
        obs_data = np.vectorize(lambda x: x.true_label)(testMat[:, :t+1])
        obs_mask = ~evidMat[:, :t+1]
        obs = np.ma.array(obs_data, mask=obs_mask)
        if last_slice_only:
            variables = [(id_, T-1) for id_ in filter(lambda x: ~evidMat[x, -1], self.sortedids)]
            inferences_dynamic = dlg.exactInferenceDynamic(mu, cova, vars=variables, T=T, obs=obs, inverse_method='SVD')
            marginal_mu, marginal_sigmasq = self._convertInferencesDynamicLastSlice(inferences_dynamic)
            marginal_mu[~obs.mask[:, -1]] = obs.data[~obs.mask[:, -1]]
            marginal_sigmasq[~obs.mask[:, -1]] = 0
        else:
            inferences_dynamic = dlg.exactInferenceDynamic(mu, cova, T=T, obs=obs, inverse_method='SVD')
            marginal_mu, marginal_sigmasq = self._convertInferencesDynamicAllSlices(inferences_dynamic, T)
            marginal_mu[~obs.mask] = obs.data[~obs.mask]
            marginal_sigmasq[~obs.mask] = 0
        return marginal_mu, marginal_sigmasq

    def _convertParents(self):
        '''It converts parents data from pgmai format to PyCK format'''
        parentsNew = dict()
        for var in self.sortedids:
            parentsNew[var] = map(lambda x: (x, 0) if x < self.rvCount else (x - self.rvCount, -1),
                                  self.parentDict[var])
        return parentsNew

    def _convertInferencesDynamicAllSlices(self, inferences_dynamic, T):
        mu = np.ones((self.rvCount, T)) * (-1)
        sigmasq = np.ones((self.rvCount, T)) * (-1)
        for key in inferences_dynamic:
            mu[key[0], key[1]], sigmasq[key[0], key[1]] = inferences_dynamic[key]
        return mu, sigmasq

    def _convertInferencesDynamicLastSlice(self, inferences_dynamic):
        mus = np.ones((self.rvCount,)) * -1
        sigmasqs = np.ones((self.rvCount,)) * -1
        for key in inferences_dynamic:
            mus[key[0]], sigmasqs[key[0]] = inferences_dynamic[key]
        return mus, sigmasqs

    def computeVar(self, evidMat):
        T = evidMat.shape[1]
        varMat = np.empty(shape=(self.rvCount,T), dtype=np.float_)
        # varMat[self.sortedids[0], 0] = 0 if evidMat[self.sortedids[0], 0] else self.cpdParams[self.sortedids[0]][0][2]
        for sensor in self.sortedids:  # [1:]:
            if evidMat[sensor, 0]:
                varMat[sensor, 0] = 0
            else:
                currentVar = self.cpdParams[sensor][0][2]
                currentTimeParents = self.parentDict[sensor][:-1]
                varVec = varMat[currentTimeParents, 0]
                varMat[sensor,0] = np.dot(varVec, (self.cpdParams[sensor][0][1] ** 2)) + currentVar
        for t in range(1,T):
            for sensor in self.sortedids:
                if evidMat[sensor, t]:
                    varMat[sensor, t] = 0
                else:
                    currentVar = self.cpdParams[sensor][1][2]
                    varVec = np.empty(shape=len(self.parentDict[sensor]))
                    currentTimeParents = self.parentDict[sensor][:-1]
                    varVec[:-1] = varMat[currentTimeParents, t]
                    previousTimeParent = self.parentDict[sensor][-1]
                    varVec[-1] = varMat[previousTimeParent - self.rvCount, t-1]
                    varMat[sensor,t] = np.dot(varVec, (self.cpdParams[sensor][1][1] ** 2)) + currentVar
        return varMat[:, -1]

    def predict_incorrect(self, testset, evidence_mat=None):
        Y_true = np.vectorize(lambda x: x.true_label)(testset)
        if evidence_mat is None:
            evidence_mat = np.zeros(testset.shape,dtype=np.bool8)
        else:
            assert(testset.shape == evidence_mat.shape)
        Y_pred = np.empty(shape=testset.shape,dtype=np.float64)
        for currentid in self.sortedids:
            (b0,b,var) = self.cpdParams[currentid,0]
            parents = self.parentDict[currentid][:-1]
            if parents == []:
                currentmean = b0
            else:
                parentValues = Y_pred[:,0]
                evidCurTime = evidence_mat[:,0]
                parentValues[parents][evidCurTime[parents]] = Y_true[parents,0][evidCurTime[parents]]
                parentValues = parentValues[parents]
                currentmean = b0 + np.dot(b.T,parentValues)
            Y_pred[currentid,0] = currentmean
        for t in xrange(1,testset.shape[1]):
            for currentid in self.sortedids:
                (b0,b,var) = self.cpdParams[currentid,1]
                parents = self.parentDict[currentid][:-1]
                parentValuesT = Y_pred[:,t]
                evidCurTime = evidence_mat[:,t]
                parentValuesT[parents][evidCurTime[parents]] = Y_true[parents,t][evidCurTime[parents]]
                if evidence_mat[currentid,t-1]:
                    itselfPrevious = Y_true[currentid,t-1]
                else:
                    itselfPrevious = Y_pred[currentid,t-1]
                parentValuesT = parentValuesT[parents]
                parentValues = np.append(parentValuesT, itselfPrevious)
                currentmean = b0 + np.dot(b.T,parentValues)
                Y_pred[currentid,t] = currentmean
        return Y_pred

    def predictTrial(self,testset, evidence_mat=None):
        Y_true = np.vectorize(lambda x: x.true_label)(testset)
        if evidence_mat is None:
            evidence_mat = np.zeros(testset.shape,dtype=np.bool8)
        else:
            assert(testset.shape == evidence_mat.shape)
        Y_pred = np.empty(shape=testset.shape,dtype=np.float64)
        (sampleStorage,weightList, logWeightList) = \
                self.likelihoodWeighting(evidence_mat, testset, sampleSize = 10)
        for i in xrange(Y_pred.shape[0]):
            for j in xrange(Y_pred.shape[1]):
                try:
                    Y_pred[i,j] = np.dot(sampleStorage[:,i,j],logWeightList)/np.sum(logWeightList)
                except ValueError as valueError:
                    print valueError
        return Y_pred

#     def compute_mean_absolute_error(self,test_set,Y_pred, type_=0, evidence_mat=None):
#         super(GaussianDBN,self).compute_mean_absolute_error(test_set,Y)

    def compute_accuracy(self, Y_test, Y_pred):
        raise NotImplementedError('Method compute_accuracy() is not yet implemented.')

    def compute_confusion_matrix(self, Y_test, Y_pred):
        raise NotImplementedError('Method compute_confusion_matrix() is not yet implemented.')

    def checkParentChildOrder(self):
        for i in xrange(len(self.sortedids)):
            curid = self.sortedids[i]
            try:
                parentset = set(self.parentDict[curid])
            except KeyError:
                continue
            if not parentset.issubset(self.sortedids[:i]):
                raise ValueError('parents are not in former positions for '+
                                 str(curid))

    def forwardSampling(self, evidMat, testMat, sampleSize = 10000, T=96):
        rvCount = len(self.sortedids)
        sampleStorage = np.empty(shape = (sampleSize,len(self.sortedids),T),
                                     dtype=np.float64)
        for currentSample in xrange(sampleSize):
            print currentSample
            for currentid in self.sortedids:
                if evidMat[currentid,0]:
                    sampleStorage[currentSample,currentid,0] = testMat[currentid,0]
                else:
                    (b0,b,var) = self.cpdParams[currentid,0]
                    parents = self.parentDict[currentid][:-1]
                    if parents == []:
                        currentmean = b0
                    else:
                        parentValues = sampleStorage[currentSample,parents,0]
                        currentmean = b0 + np.dot(b.T,parentValues)
                    sampleStorage[currentSample,currentid,0] = \
                        np.random.normal(currentmean,var**.5)
            for t in xrange(1,T):
    #             print '\t',t
                for currentid in self.sortedids:
                    if evidMat[currentid,t]:
                        sampleStorage[currentSample,currentid,t] = testMat[currentid,t]
                    else:
        #                 print '\t\t',currentid
                        parents = self.parentDict[currentid]
        #                 print 'parents',parents
                        (b0,b,var) = self.cpdParams[currentid,1]
        #                 print (b0,b,var)
                        parentValuesT = sampleStorage[currentSample,parents[:-1],t]
        #                 print 'parentValuesT',parentValuesT
                        itselfPrevious = sampleStorage[currentSample,parents[-1]-rvCount,t-1]
        #                 print 'itselfPrevious',itselfPrevious
                        parentValues = np.append(parentValuesT, itselfPrevious)
#                         print 'parentValues',parentValues
                        currentmean = b0 + np.dot(b.T,parentValues)
                        sampleStorage[currentSample,currentid,t] = \
                            np.random.normal(currentmean,var**.5)
        return sampleStorage

    def getChildDict(self):
#         rvids = np.array(self.parentDict.keys())
#         rvCount = rvids.shape[0]
        childDict = dict()
        for key in self.sortedids:
            childDict[key] = list()
        for key in self.sortedids:
            for val in self.parentDict[key]:
                if val < self.rvCount:
                    childDict[val].append(key)
                else:
                    childDict[val - self.rvCount].append(key + self.rvCount)
        return childDict

def testPredictIncorrect():
    topology = 'mst'
    start = time()
    trainset,testset = convert_time_window_df_randomvar_hour(True,
                            Neighborhood.itself_previous_others_current)
    gdbn = GaussianDBN()
    gdbn.fit(trainset, topology=topology)
    Y_pred = gdbn.predict_incorrect(testset)
    print 'End of process. Duration: {}'.format(time()-start)

