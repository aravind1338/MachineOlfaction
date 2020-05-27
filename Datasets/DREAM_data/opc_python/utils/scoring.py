import numpy as np
from scipy.stats import pearsonr
from . import loading

from __init__ import *
SIGMAS = {'int': 0.0187,
          'ple': 0.0176,
          'dec': 0.0042}

SIGMAS2 = {'int_mean': 0.1193,
           'ple_mean': 0.1265,
           'dec_mean': 0.0265,
           'int_std': 0.1194,
           'ple_std': 0.1149,
           'dec_std': 0.0281}

# Scoring for sub-challenge 1.
def r(kind,predicted,observed,n_subjects=49,mask=True):
    # Predicted and observed should each be an array of 
    # molecules by perceptual descriptors by subjects
    
    r = 0.0
    for subject in range(1,n_subjects+1):
        p = predicted[subject].unstack('Descriptor')
        o = observed[subject].unstack('Descriptor')
        r += r2(kind,None,p,o,mask=mask)
    r /= n_subjects
    return r

def score(predicted,observed,n_subjects=49):
    """Final score for sub-challenge 1."""
    score = z('int',predicted,observed,n_subjects=n_subjects) \
          + z('ple',predicted,observed,n_subjects=n_subjects) \
          + z('dec',predicted,observed,n_subjects=n_subjects)
    return score/3.0

def score_summary(predicted,observed,mask=True):
    score_ = score(predicted,observed)
    r_int = r('int',predicted,observed,mask=mask)
    r_ple = r('ple',predicted,observed,mask=mask)
    r_dec = r('dec',predicted,observed,mask=mask)
    return 'Score: %3f; rs = %.3f,%.3f,%.3f' % \
                (score_, r_int, r_ple, r_dec)

def rs2score(r_int,r_ple,r_dec):
    z_int = r_int/SIGMAS['int']
    z_ple = r_ple/SIGMAS['ple']
    z_dec = r_dec/SIGMAS['dec']
    return (z_int+z_ple+z_dec)/3.0

def z(kind,predicted,observed,n_subjects=49): 
    std = SIGMAS[kind]
    shuffled_r = 0#r2(kind,predicted,shuffled)
    observed_r = r(kind,predicted,observed,n_subjects=n_subjects)
    return (observed_r - shuffled_r)/std

# Scoring for sub-challenge 2.  

def r2(kind,moment,predicted,observed,mask=False):
    # Predicted and observed should each be an array of 
    # molecules by 2*perceptual descriptors (means then stds)
    descriptors = loading.get_descriptors(format=True)
    if moment == 'mean':
        try:
            p = predicted['mean']
        except KeyError:
            p = predicted.mean(axis=1)
        p = p.unstack('Descriptor')
        o = observed.mean(axis=1).unstack('Descriptor')
    elif moment == 'std':
        try:
            p = predicted['std']
        except KeyError:
            p = predicted.std(axis=1)
        p = p.unstack('Descriptor')
        o = observed.std(axis=1).unstack('Descriptor')
    elif moment is None:
        p = predicted
        o = observed
    else:
        raise ValueError('No such moment: %s' % moment)
    
    if kind=='int':
        p = p['Intensity']
        o = o['Intensity']
    elif kind=='ple':
        p = p['Pleasantness']
        o = o['Pleasantness']
    elif kind == 'dec':
        p = p.drop(['Intensity','Pleasantness'],1)
        o = o.drop(['Intensity','Pleasantness'],1)
    elif kind in descriptors:
        p = p[kind]
        o = o[kind]
    elif kind is None:
        p = p
        o = o
    else:
        raise ValueError('No such kind: %s' % kind)
    
    common_CIDs = list(set(p.index.values).intersection(o.index.values))
    p = p.loc[common_CIDs].values
    o = o.loc[common_CIDs].values

    if len(p.shape)==1:
        p = p.reshape(-1,1)
    if len(o.shape)==1:
        o = o.reshape(-1,1)
    r = 0.0
    cols = p.shape[1]
    denom = 0.0
    for i in range(cols):
        p_ = p[:,i]
        o_ = o[:,i]
        if mask:
            r_ = np.ma.corrcoef(p_,o_)[0,1]
            if ('%f' % r_) == 'nan':
                denom += 1 # Done to match DREAM scoring.  
                continue
        else:
            r_ = pearsonr(p_,o_)[0]
            if np.isnan(r_):
                denom += 1 # Done to match DREAM scoring.  
                #print('NaN')
                if np.std(p_)*np.std(o_) != 0:
                    pass#print('WTF')
                continue
        r += r_
        denom += 1
    if denom == 0.0:
        r = np.nan
    else:
        r /= denom
    return r

def score2(predicted,observed):
    """Final score for sub-challenge 2."""
    score = z2('int','mean',predicted,observed) \
          + z2('ple','mean',predicted,observed) \
          + z2('dec','mean',predicted,observed) \
          + z2('int','std',predicted,observed) \
          + z2('ple','std',predicted,observed) \
          + z2('dec','std',predicted,observed)
    return score/6.0

def score_summary2(predicted,observed,mask=False):
    score = score2(predicted,observed)
    r_int_mean = r2('int','mean',predicted,observed,mask=mask)
    r_ple_mean = r2('ple','mean',predicted,observed,mask=mask)
    r_dec_mean = r2('dec','mean',predicted,observed,mask=mask)
    r_int_std = r2('int','std',predicted,observed,mask=mask)
    r_ple_std = r2('ple','std',predicted,observed,mask=mask)
    r_dec_std = r2('dec','std',predicted,observed,mask=mask)
    return 'Score: %3f; rs = %.3f,%.3f,%.3f,%.3f,%.3f,%.3f' % \
                (score, r_int_mean, r_ple_mean, r_dec_mean, \
                        r_int_std,r_ple_std,r_dec_std)

def rs2score2(rs):
    z = 0
    for kind in ['int','ple','dec']:
        for moment in ['mean','std']:
            z += rs[kind][moment]/SIGMAS2[kind+'_'+moment]
    return z/6.0

def z2(kind,moment,predicted,observed): 
    std = SIGMAS2[kind+'_'+moment]
    shuffled_r = 0#r2(kind,predicted,shuffled)
    observed_r = r2(kind,moment,predicted,observed)
    return (observed_r - shuffled_r)/std

def scorer2(estimator,inputs,observed):
    predicted = estimator.predict(inputs)
    return r2(None,None,predicted,observed)