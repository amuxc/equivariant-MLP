import torch
import torch.nn as nn
import copy
import numpy as np
import objax.nn as nn
import jax
from jax import jit
import jax.numpy as jnp
from emlp_jax.equivariant_subspaces import size,TensorRep
import logging
import objax.functional as F
from functools import partial
import objax

def gate_indices(rep):
    channels = rep.size()
    indices = np.arange(channels)
    num_nonscalars = 0
    i=0
    for rank in rep.ranks:
        if rank!=(0,0):
            indices[i:i+size(rank,rep.d)] = channels+num_nonscalars
            num_nonscalars+=1
        i+=size(rank,rep.d)
    return indices

def scalar_mask(rep):
    channels = rep.size()
    mask = np.ones(channels)>0
    i=0
    for rank in rep.ranks:
        if rank!=(0,0): mask[i:i+size(rank,rep.d)] = False
        i+=size(rank,rep.d)
    return mask

# class TensorMaskBN(nn.BatchNorm0D): #TODO find discrepancies with pytorch version
#     """ Equivariant Batchnorm for tensor representations.
#         Applies BN on Scalar channels and Mean only BN on others """
#     def __init__(self,rep):
#         super().__init__(rep.size(),momentum=0.9)
#         self.rep=rep
#         #self.extra_loss = objax.StateVar(jnp.array(0.))
#     def __call__(self,x,training):
#         #logging.debug(f"bn input shape{inp.shape}")
#         #self.extra_loss.value=jnp.array(0.)
#         if training:
#             m = x.mean(self.redux, keepdims=True)
#             v = (x ** 2).mean(self.redux, keepdims=True) - m ** 2
#             self.running_mean.value += (1 - self.momentum) * (m - self.running_mean.value)
#             self.running_var.value += (1 - self.momentum) * (v - self.running_var.value)
#             #self.extra_loss.value = ((jnp.sqrt(v)-1)**2).sum()#1e-1*((m**2) + ).sum()
#         else:
#             m, v = self.running_mean.value, self.running_var.value
#         smask = jax.device_put(scalar_mask(self.rep))
#         y = jnp.where(smask,self.gamma.value * (x - m) * F.rsqrt(v + self.eps) + self.beta.value,(x-m))#*F.rsqrt(v + self.eps))
#         return y # switch to or (x-m)

class TensorMaskBN(nn.BatchNorm0D): #TODO find discrepancies with pytorch version
    """ Equivariant Batchnorm for tensor representations.
        Applies BN on Scalar channels and Mean only BN on others """
    def __init__(self,rep):
        super().__init__(rep.size(),momentum=0.9)
        self.rep=rep
        # object_wise_tensor_prod_rep = TensorRep([(2*p,2*q) for p,q in rep.ranks],rep.G)
        # self.dual_rep = object_wise_tensor_prod_rep.T
        # b = self.dual_rep.symmetric_projection()(np.random.randn(self.dual_rep.size()))
        # self.bilinear = []
        # i=0
        # for rank in self.dual_rep.ranks:
        #     v = b[i:i+size(rank,rep.d)]
        #     self.bilinear.append(v / jnp.abs(v).mean())
        #     i+= size(rank,rep.d)
        # self.bilinear = jnp.concatenate(self.bilinear)

    def __call__(self,x,training):
        #logging.debug(f"bn input shape{inp.shape}")
        #self.extra_loss.value=jnp.array(0.)
        smask = jax.device_put(scalar_mask(self.rep))
        if training:
            m = x.mean(self.redux, keepdims=True)
            v = (x ** 2).mean(self.redux, keepdims=True) - m ** 2
            #fill in objectwise prod
            #oo = jnp.zeros_like(self.bilinear)[None].repeat(x.shape[0],0)#
            #oo = objectwise_outer_prod(x,self.rep)
            #logging.warning(f"oo shape {oo.shape}")
            #vbilinear = jnp.abs(ragged_gather_scatter(self.bilinear*oo,self.dual_rep)) # scalar, we can do whatever
            #v = jnp.where(smask,v,vbilinear)
            self.running_mean.value += (1 - self.momentum) * (m - self.running_mean.value)
            self.running_var.value += (1 - self.momentum) * (v - self.running_var.value)
            #self.extra_loss.value = ((jnp.sqrt(v)-1)**2).sum()#1e-1*((m**2) + ).sum()
        else:
            m, v = self.running_mean.value, self.running_var.value
        
        
        y = jnp.where(smask,self.gamma.value * (x - m) * F.rsqrt(v + self.eps) + self.beta.value,x)#(x-m)*F.rsqrt(v + self.eps))
        return y # switch to or (x-m)


class MaskBN(nn.BatchNorm0D): #TODO find discrepancies with pytorch version
    """ Equivariant Batchnorm for tensor representations.
        Applies BN on Scalar channels and Mean only BN on others """
    def __init__(self,ch):
        super().__init__(ch,momentum=0.9)

    def __call__(self,vals,mask,training=True):
        sum_dims = list(range(len(vals.shape[:-1])))
        x_or_zero = jnp.where(mask[...,None],vals,0*vals)
        if training:
            num_valid = mask.sum(sum_dims)
            m = x_or_zero.sum(sum_dims)/num_valid
            v = (x_or_zero ** 2).sum(sum_dims)/num_valid - m ** 2
            self.running_mean.value += (1 - self.momentum) * (m - self.running_mean.value)
            self.running_var.value += (1 - self.momentum) * (v - self.running_var.value)
        else:
            m, v = self.running_mean.value, self.running_var.value
        return ((x_or_zero-m)*self.gamma.value*F.rsqrt(v + self.eps) + self.beta.value,mask)

#@partial(jit,static_argnums=(1,))
def objectwise_outer_prod(x,x_rep):
    """ This routine is super slow at compiling for unknown reason"""
    y = []
    i=0
    for rank in x_rep.ranks:
        v = x[:,i:i+size(rank,x_rep.d)]
        y.append((v[:,:,None]*v[:,None,:]).reshape(x.shape[0],-1))
        i+=size(rank,x_rep.d)
    return jnp.concatenate(y,-1)

@partial(jit,static_argnums=(1,))
def ragged_gather_scatter(x,x_rep):
    y = []
    i=0
    for rank in x_rep.ranks:
        y.append(x[:,i:i+size(rank,x_rep.d)].sum(keepdims=True).repeat(x_rep.d**(sum(rank)//2),axis=-1))
        i+=size(rank,x_rep.d)
    return jnp.concatenate(y,-1)


def capped_tensor_ids(repin,maxrep):
    """Returns rep and ids for tensor product repin@repin
       but with terms >repin removed """
    product_rep = (repin*repin)
    tensor_multiplicities = product_rep.multiplicities()
    multiplicities = maxrep.multiplicities()
    min_mults = collections.OrderedDict((rank,min(tm,multiplicities[rank]))
                                        for rank,tm in tensor_multiplicities.items())
    # randomly select up to maxrep from each of the tensor ranks
    within_ids = collections.OrderedDict((rank,np.random.choice(v,min(v,multiplicities[rank])))
                                                for rank,v in tensor_multiplicities.items())
    all_ids= []
    i_all = 0
    d = repin.d
    for (p,q),ids in within_ids.items():
        interleaved_ids = (d**(p+q)*ids[:,None]+np.arange(d**(p+q))).reshape(-1)
        all_ids.extend(interleaved_ids+i_all)
        i_all += tensor_multiplicities[(p,q)]*d**(p+q)
    sorted_perm = product_rep.argsort()
    out_ranks = []
    for rank,mul in min_mults.items():
        out_ranks.extend(mul*[rank])
    out_rep = TensorRep(out_ranks,G=repin.G)
    # have to do some gnarly permuting to account for block ordering vs elemnt ordering
    # and then the multiplicity sorted order and the original ordering
    ids = jnp.argsort(rep_permutation(product_rep))[sorted_perm[all_ids]]
    return out_rep,ids