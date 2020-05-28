import sys, os, io, pstats
import numpy as np
import cProfile
from time import time
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.ticker import NullFormatter
# Disable
def blockPrint():
    sys.stdout = open(os.devnull, 'w')

# Restore
def enablePrint():
    sys.stdout = sys.__stdout__

def profile(fnc):
    """A decorator that uses cProfile to profile a function"""

    def inner(*args, **kwargs):
        pr = cProfile.Profile()
        pr.enable()
        retval = fnc(*args, **kwargs)
        pr.disable()
        s = io.StringIO()
        sortby = 'cumulative'
        ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        ps.print_stats()
        print(s.getvalue())
        return retval

    return inner

def shannon_entropy(Di, sigma=1.0):
    """
    Compute shannon entropy Hi and corresponding Pi-row of the i'th object
    Note: sigma can be seen as squared in this method
    """
    # print('distance: ' + str(Di))
    Pj = np.exp(-Di.copy() / (2 * sigma))  # the j elements of the "i'th" row
    # print(Pj)
    sumP = sum(Pj)
    Pi = Pj / sumP

    Hj = np.log(Pi) * Pi
    # print(Hj)
    Hi = -np.sum(Hj)
    # print('H: ' + str(H))
    return Hi, Pi

def cond_probs(X=np.array([]), tol=1e-5, perplexity=30):
    """
    Find the conditional probabilities Pj|i such that each gaussian
    has the same perplexity of an NxD matrix
    """
    print("Start computing conditional probabilities...")
    # initialize variables
    begin = time()
    (n, d) = X.shape
    P = np.zeros((n, n))  # the conditional probability matrix
    sigma = np.ones((n, 1))
    logU = np.log(perplexity)

    print("computing pairwaise distances...")
    t0 = time()
    sum_X_squared = np.sum(np.square(X), 1)
    D = np.add(np.add(-2 * np.dot(X, X.T), sum_X_squared).T, sum_X_squared)  # distance matrix
    print("Computing pairwise distances took %8.2f seconds" % (time() - t0))

    print("starting binary search...")
    t0 = time()
    # Compute the conditonal probabilities
    for i in range(n):

        # Print progress
        if i % 500 == 0:
            print("Computing P-values for point %d of %d..." % (i, n))

        # Compute the Gaussian kernel and entropy for the current precision
        sigma_min = -np.inf
        sigma_max = np.inf
        Di = D[i, np.concatenate((np.r_[0:i], np.r_[i + 1:n]))]
        (H, thisP) = shannon_entropy(Di, sigma[i])

        # Evaluate whether the perplexity is within tolerance
        Hdiff = H - logU
        tries = 0
        while np.abs(Hdiff) > tol and tries < 50:
            # note: H is monotonically increasing in sigma
            if Hdiff < 0:  # increase sigma
                sigma_min = sigma[i].copy()
                if sigma_max == np.inf or sigma_max == -np.inf:  # if we dont have a value for sima_max yet
                    sigma[i] = sigma[i] * 2.
                else:
                    sigma[i] = (sigma[i] + sigma_max) / 2.
            else:  # decrease sigma
                sigma_max = sigma[i].copy()
                if sigma_min == np.inf or sigma_min == -np.inf:
                    sigma[i] = sigma[i] / 2.
                else:
                    sigma[i] = (sigma[i] + sigma_min) / 2.
            # print('sigma max' + str(sigma_max))
            # print('sigma min' + str(sigma_min))
            # print(sigma[i])
            # Recompute the values
            (H, thisP) = shannon_entropy(Di, sigma[i])
            Hdiff = H - logU
            # print(Hdiff)
            tries += 1

        # Set the final row of P
        P[i, np.concatenate((np.r_[0:i], np.r_[i + 1:n]))] = thisP
    print("binary search took %8.2f seconds" % (time() - t0))
    print("Finding all conditional probabilities took %8.2f seconds" % (time() - begin))
    # Return final P-matrix
    print("Mean value of sigma: %f" % np.mean(np.sqrt(sigma)))
    return P, sigma #note: sigma is squared version

def joint_average_P(cond_P):
    """
    Compute the joint probability matrix according to Pij = Pji =(Pi|j + Pj|i)/2

    """
    (n, d) = cond_P.shape
    P = (cond_P + np.transpose(cond_P)) / (2 * n)
    P = np.maximum(P, 1e-12)
    # P = P/np.sum(P) #normalize the probabilities
    # print('sum of P is ' + str(np.sum(P)))

    return P

def joint_Q(Y, dof=1.):
    """
    Compute the joint probabilities qij of the low dimensional data Y according to the student-t with dof 1
    """
    (n, d) = Y.shape
    ''' 
    sum_Y_squared = np.sum(np.square(Y), 1)
    D = np.add(np.add(-2 * np.dot(Y, Y.T), sum_Y_squared).T, sum_Y_squared) 
    num = 1./ (1.+ D) # numerator of qij
    num[range(n), range(n)] = 0 #qii are 0
    Q = num/np.sum(num) #normalize
    '''

    sum_Y_squared = np.sum(np.square(Y), 1)
    num = -2. * np.dot(Y, Y.T)
    num = ((dof+1.)/2) / (1. + (np.add(np.add(num, sum_Y_squared).T, sum_Y_squared))/dof)  # numerator of qij: (1 + ||yi -yj||^2)^-1
    num[range(n), range(n)] = 0.
    Q = num / np.sum(num)
    Q = np.maximum(Q, 1e-12)
    return Q, num

def pca(X=np.array([]), no_dims=50):
    """
        Runs PCA on the NxD array X in order to reduce its dimensionality to
        no_dims dimensions for preprocessing.
    """
    print("Preprocessing the data using PCA...")
    t0 = time()
    (n, d) = X.shape
    X = X - np.tile(np.mean(X, 0), (n, 1))
    (l, M) = np.linalg.eig(np.dot(X.T, X))
    Y = np.dot(X, M[:, 0:no_dims])
    print("Reducing dimension of data with PCA took: %8.2f seconds" % (time() - t0))
    return Y

def gauss_kernel(x, X, sigma):
    '''
    Calculates the gaussian kernel function for each
    row of X respect to x. sigma is calculated via
    the binary search and perplexity.
        (m, d) = x.shape
    (n, D) = X.shape


    '''
    (n, D) = X.shape
    '''' 
    x = x.reshape((1, D))
    k = np.exp(-(np.sum((x - X)**2, axis=1)**2))/(2.*sigma.reshape((1,n)))
    '''
    k = np.zeros(n)

    for i in range(n):
        k[i] = np.exp(-(np.linalg.norm(x - X[i,:])**2)/(2.*sigma[i]))
    return k

def plot(Y, labels, title='',marker = None ,label = False, cmap = 'Paired', s=15, save_path=None, linewidth=1):
    fig, ax = plt.subplots()

    if marker == None:
        scatter = ax.scatter(Y[:, 0], Y[:, 1], c=labels,cmap=cmap , s=s)
    else:
        cmap = cm.get_cmap(cmap, len(marker))
        for i, e in enumerate(marker):

            ax.scatter(Y[:,0][labels==i], Y[:,1][labels==i], s=s, linewidths= linewidth, marker = '$'+marker[i]+'$' )
    #ax.set_xlabel('dim 1')
    #ax.set_ylabel('dim 2')
    ax.set_title(title)
    #ax.xaxis.set_major_formatter(NullFormatter())
    #ax.yaxis.set_major_formatter(NullFormatter())
    fig.patch.set_visible(False)
    ax.axis('off')
    if label:
        plt.legend(*scatter.legend_elements(), loc="upper right", title='Labels', prop={'size': 6}, fancybox=True)
    fig.tight_layout()
    if save_path != None:
        plt.savefig(save_path)
    plt.show()

def make_dir(file_path):
    split = file_path.rsplit('/',1)
    dir = split[0]
    import os
    if not os.path.exists(dir):
        os.makedirs(dir)
    return split
