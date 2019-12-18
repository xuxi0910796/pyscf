#!/usr/bin/env python

'''
Analytical nuclear gradient for constrained nuclear-electronic orbital
'''
import numpy
from pyscf import scf
from pyscf import grad

class Gradients():
    '''
    Example:

    >>> mol = neo.Mole()
    >>> mol.build(atom = 'H 0 0 0.00; C 0 0 1.064; N 0 0 2.220', basis = 'ccpvtz')
    >>> mol.set_quantum_nuclei([0])
    >>> mol.set_nuclei_expect_position(mol.atom_coord(0), unit='B')
    >>> mf = neo.CDFT(mol)
    >>> mf.mf_elec.xc = 'b3lyp'
    >>> mf.inner_scf()

    >>> g = neo.Gradients(mf)
    >>> g.kernel()
    '''

    def __init__(self, scf_method):
        self.mol = scf_method.mol
        self.base = scf_method
        atmlst = self.mol.quantum_nuc
        self.atmlst = [i for i in range(len(atmlst)) if atmlst[i] == False] # a list for classical nuclei

    def grad_elec(self, atmlst=None):
        g = self.base.mf_elec.nuc_grad_method()
        return g.grad(atmlst = atmlst)

    def hcore_deriv(self, atm_id): #beta
        mol = self.mol.nuc
        aoslices = mol.aoslice_by_atom()
        shl0, shl1, p0, p1 = aoslices[atm_id]
        with mol.with_rinv_as_nucleus(atm_id):
            vrinv = mol.intor('int1e_iprinv', comp=3) # <\nabla|1/r|>
            vrinv *= mol.atom_charge(atm_id)

        return vrinv + vrinv.transpose(0,2,1)

    def make_rdm1e(self):
        mo_energy = self.base.mf_nuc.mo_energy
        mo_coeff = self.base.mf_nuc.mo_coeff
        mo_occ = self.base.mf_nuc.occ

        mo0 = mo_coeff[:,mo_occ>0]
        mo0e = mo0 * (mo_energy[mo_occ>0] * mo_occ[mo_occ>0])
        return numpy.dot(mo0e, mo0.T.conj())

    def grad_jcross(self):
        'get the gradient for the cross term of Coulomb interactions between electrons and quantum nuclei'
        jcross = scf.jk.get_jk((self.mol.elec, self.mol.elec, self.mol.nuc, self.mol.nuc), self.base.dm_nuc, scripts='ijkl,lk->ij', intor='int2e_ip1_sph', comp=3)
        return -jcross

    def grad_quantum_nuc(self):
        'JCP, ...'
        return -self.base.f

    def kernel(self, atmlst=None):
        if atmlst == None:
            atmlst = range(self.mol.natm)
        de = numpy.zeros((len(atmlst), 3))

        aoslices = self.mol.aoslice_by_atom()
        jcross = self.grad_jcross()

        for k, ia in enumerate(atmlst):
            if self.mol.quantum_nuc[ia] == True:
                de[k] = self.grad_quantum_nuc()
            else:
                p0, p1 = aoslices[ia,2:]
                h1ao = self.hcore_deriv(ia)
                de[k] += numpy.einsum('xij,ij->x', h1ao, self.base.dm_nuc)
                de[k] -= numpy.einsum('xij,ij->x', jcross[:,p0:p1], self.base.dm_elec[p0:p1]) * 2

        grad_elec = self.grad_elec(atmlst = self.atmlst)
        de[self.atmlst] += grad_elec
        return de

