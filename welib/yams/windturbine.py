"""
Generic wind turbine class for structural models
based on Generic bodies classes

Intended to be used by other models such as TNSB, FNTSB, for yams_rec, yams_sympy
Unification not done yet.

Example:

    WT = WindTurbineStructure.fromFAST('Main.fst')
    print(WT.nac)
    print(WT.twr)
    print(WT.RNA)
"""

import os
import numpy as np
import copy
import welib.weio as weio
from collections import OrderedDict
from welib.yams.utils import R_x, R_y, R_z
from welib.yams.bodies import RigidBody, FlexibleBody, FASTBeamBody

class WindTurbineStructure():
    def __init__(self):
        self.hub = None
        self.gen = None
        self.nac = None
        self.twr = None

    @staticmethod
    def fromFAST(fstFilename):
        return FASTWindTurbine(fstFilename)

    @property
    def q0(self):
        return np.array([dof['q0'] for dof in self.DOF if dof['active']])
    @property
    def qd0(self):
        return np.array([dof['qd0'] for dof in self.DOF if dof['active']])
    @property
    def DOFname(self):
        return np.array([dof['name'] for dof in self.DOF if dof['active']])

    @property
    def activeDOFs(self):
        return [dof for dof in self.DOF if dof['active']]

    @property
    def channels(self):
        """ """
#         for dof in self.DOF:
#             if dof['q_channel'] is None:
#                 chan.append(dof['name'])
#             elif hasattr(dof['q_channel'] , __len__):
# 
#             if 
        chan = [dof['q_channel'] if dof['q_channel'] is not None else dof['name']  for dof in self.DOF if dof['active']]
        chan+= [dof['qd_channel'] if dof['qd_channel'] is not None else 'd'+dof['name'] for dof in self.DOF if dof['active']]
        return chan


# --------------------------------------------------------------------------------}
# --- Helpers 
# --------------------------------------------------------------------------------{
def rigidBlades(blds, hub=None, r_O=[0,0,0]):
    """ return a rigid body for the three blades
    All bodies should be in a similar frame
    """
    blades = blds[0].toRigidBody()
    for B in blds[1:]:
        B_rigid = B.toRigidBody()
        blades = blades.combine(B_rigid, r_O=r_O)
    blades.name='blades'
    return blades


# --------------------------------------------------------------------------------}
# --- Converters 
# --------------------------------------------------------------------------------{
def FASTWindTurbine(fstFilename, main_axis='z', nSpanTwr=None, twrShapes=None, algo=''):
    """

    """
    # --- Reading main OpenFAST files
    ext     = os.path.splitext(fstFilename)[1]
    FST     = weio.read(fstFilename)
    rootdir = os.path.dirname(fstFilename)
    EDfile  = os.path.join(rootdir,FST['EDFile'].strip('"')).replace('\\','/')
    ED      = weio.read(EDfile)
    rootdir = os.path.dirname(EDfile)
    bldfile = os.path.join(rootdir,ED['BldFile(1)'].strip('"')).replace('\\','/')
    twrfile = os.path.join(rootdir,ED['TwrFile'].strip('"')).replace('\\','/')
    # TODO SubDyn, MoorDyn, BeamDyn 

    # Basic geometries for nacelle
    theta_tilt_y = -ED['ShftTilt']*np.pi/180  # NOTE: tilt has wrong orientation in FAST
    R_NS = R_y(theta_tilt_y)  # Rotation fromShaft to Nacelle
    r_NS_inN    = np.array([0             , 0, ED['Twr2Shft']]) # Shaft start in N
    r_SR_inS    = np.array([ED['OverHang'], 0, 0             ]) # Rotor center in S
    r_SGhub_inS = np.array([ED['HubCM']   , 0, 0             ]) + r_SR_inS # Hub G in S
    r_NR_inN    = r_NS_inN + R_NS.dot(r_SR_inS)                 # Rotor center in N
    r_NGnac_inN = np.array([ED['NacCMxn'],0,ED['NacCMzn']    ]) # Nacelle G in N
    r_RGhub_inS = - r_SR_inS + r_SGhub_inS
    if main_axis=='x':
        raise NotImplementedError()

    # --- Hub  (defined using point N and nacelle coord as ref)
    M_hub  = ED['HubMass']
    JxxHub_atR = ED['HubIner']
    hub = RigidBody('Hub', M_hub, (JxxHub_atR,0,0), s_OG=r_SGhub_inS, R_b2g=R_NS, s_OP=r_SR_inS, r_O=r_NS_inN) 

    # --- Generator (Low speed shaft) (defined using point N and nacelle coord as ref)
    gen = RigidBody('Gen', 0, (ED['GenIner']*ED['GBRatio']**2,0,0), s_OG=[0,0,0], R_b2g=R_NS,  r_O=r_NS_inN) 

    # --- Nacelle (defined using point N and nacelle coord as ref)
    M_nac = ED['NacMass']
    JyyNac_atN = ED['NacYIner'] # Inertia of nacelle at N in N
    nac = RigidBody('Nac', M_nac, (0,JyyNac_atN,0), r_NGnac_inN, s_OP=[0,0,0])

    # --- Blades 
    bldFile = weio.read(bldfile)
    m    = bldFile['BldProp'][:,3]
    jxxG = m     # NOTE: unknown
    nB = ED['NumBl']
    bld=np.zeros(nB,dtype=object)
    bld[0] = FASTBeamBody(ED, bldFile, Mtop=0, main_axis=main_axis, jxxG=jxxG, spanFrom0=False) 
    for iB in range(nB-1):
        bld[iB+1]=copy.deepcopy(bld[0])
        bld[iB+1].R_b2g
    for iB,B in enumerate(bld):
        B.name='bld'+str(iB+1)
        psi_B= -iB*2*np.pi/len(bld) 
        if main_axis=='x':
            R_SB = R_z(0*np.pi + psi_B) # TODO psi offset and psi0
        elif main_axis=='z':
            R_SB = R_x(0*np.pi + psi_B) # TODO psi0
        R_SB = np.dot(R_SB, R_y(ED['PreCone({})'.format(iB+1)]*np.pi/180)) # blade2shaft
        B.R_b2g= R_SB

    # --- Blades (with origin R, using N as "global" ref)
    blades = rigidBlades(bld, r_O = [0,0,0])
    blades.pos_global = r_NR_inN
    blades.R_b2g      = R_NS

    # --- Rotor = Hub + Blades (with origin R, using N as global ref)
    rot = blades.combine(hub, R_b2g=R_NS, r_O=blades.pos_global)
    rot.name='rotor'

    # --- RNA
    RNA = rot.combine(gen).combine(nac,r_O=[0,0,0])
    RNA.name='RNA'
    #print(RNA)

    # --- RNA
    M_RNA = RNA.mass
    # --- Fnd (defined wrt ground/MSL "E")
#     print(FST.keys())
    M_fnd = ED['PtfmMass']
    r_OGfnd_inF = np.array([ED['PtfmCMxt'],ED['PtfmCMyt'],ED['PtfmCMzt']])
    r_OT_inF    = np.array([0             ,0             ,ED['PtfmRefzt']])
    r_TGfnd_inF = -r_OT_inF + r_OGfnd_inF
    fnd = RigidBody('fnd', M_fnd, (ED['PtfmRIner'], ED['PtfmPIner'], ED['PtfmYIner']), s_OG=r_TGfnd_inF, r_O=r_OT_inF) 

    # --- Twr
    twrFile = weio.read(twrfile)
    twr = FASTBeamBody(ED, twrFile, Mtop=M_RNA, main_axis='z', bAxialCorr=False, bStiffening=True, shapes=twrShapes, nSpan=nSpanTwr, algo=algo) # TODO options

    # --- Degrees of freedom
    DOFs=[]
    DOFs+=[{'name':'x'      , 'active':ED['PtfmSgDOF'][0] in ['t','T'], 'q0': ED['PtfmSurge']  , 'qd0':0 , 'q_channel':'PtfmSurge_[m]' , 'qd_channel':'QD_Sg_[m/s]'}]
    DOFs+=[{'name':'y'      , 'active':ED['PtfmSwDOF'][0] in ['t','T'], 'q0': ED['PtfmSway']   , 'qd0':0 , 'q_channel':'PtfmSway_[m]'  , 'qd_channel':'QD_Sw_[m/s]'}]
    DOFs+=[{'name':'z'      , 'active':ED['PtfmHvDOF'][0] in ['t','T'], 'q0': ED['PtfmHeave']  , 'qd0':0 , 'q_channel':'PtfmHeave_[m]' , 'qd_channel':'QD_Hv_[m/s]'}]

    DOFs+=[{'name':'\phi_x' , 'active':ED['PtfmRDOF'][0]  in ['t','T'], 'q0': ED['PtfmRoll']*np.pi/180  , 'qd0':0 , 'q_channel':'PtfmRoll_[deg]'  , 'qd_channel':'QD_R_[rad/s]'}]
    DOFs+=[{'name':'\phi_y' , 'active':ED['PtfmPDOF'][0]  in ['t','T'], 'q0': ED['PtfmPitch']*np.pi/180 , 'qd0':0 , 'q_channel':'PtfmPitch_[deg]' , 'qd_channel':'QD_P_[rad/s]'}]
    DOFs+=[{'name':'\phi_z' , 'active':ED['PtfmYDOF'][0]  in ['t','T'], 'q0': ED['PtfmYaw']*np.pi/180   , 'qd0':0 , 'q_channel':'PtfmYaw_[deg]'   , 'qd_channel':'QD_Y_[rad/s]'}]

    DOFs+=[{'name':'q_FA1'  , 'active':ED['TwFADOF1'][0]  in ['t','T'], 'q0': ED['TTDspFA']  , 'qd0':0 , 'q_channel':'Q_TFA1_[m]', 'qd_channel':'QD_TFA1_[m/s]'}]
    DOFs+=[{'name':'q_SS1'  , 'active':ED['TwSSDOF1'][0]  in ['t','T'], 'q0': ED['TTDspSS']  , 'qd0':0 , 'q_channel':'Q_TSS1_[m]', 'qd_channel':'QD_TSS1_[m/s]'}]
    DOFs+=[{'name':'q_FA2'  , 'active':ED['TwFADOF2'][0]  in ['t','T'], 'q0': ED['TTDspFA']  , 'qd0':0 , 'q_channel':'Q_TFA2_[m]', 'qd_channel':'QD_TFA2_[m/s]'}]
    DOFs+=[{'name':'q_SS2'  , 'active':ED['TwSSDOF2'][0]  in ['t','T'], 'q0': ED['TTDspSS']  , 'qd0':0 , 'q_channel':'Q_TSS1_[m]', 'qd_channel':'QD_TSS1_[m/s]'}]

    DOFs+=[{'name':'\\theta_y','active':ED['YawDOF'][0]   in ['t','T'], 'q0': ED['NacYaw']*np.pi/180   , 'qd0':0 ,          'q_channel':'NacYaw_[deg]' , 'qd_channel':'QD_Yaw_[rad/s]'}]
    DOFs+=[{'name':'\\psi'    ,'active':ED['GenDOF'][0]   in ['t','T'], 'q0': ED['Azimuth']*np.pi/180  , 'qd0':'RotSpeed' , 'q_channel':'Azimuth_[deg]', 'qd_channel':'RotSpeed_[rpm]'}]

    DOFs+=[{'name':'\\nu'     ,'active':ED['DrTrDOF'][0]  in ['t','T'], 'q0': 0  , 'qd0':0 , 'q_channel':'Q_DrTr_[rad]', 'qd_channel':'QD_DrTr_[rad/s]'}]

    DOFs+=[{'name':'q_Fl1'  , 'active':ED['FlapDOF1'][0]  in ['t','T'], 'q0': ED['OOPDefl']  , 'qd0':0 , 'q_channel':'Q_B1F1_[m]', 'qd_channel':'QD_B1F1_[m/s]'}]
    DOFs+=[{'name':'q_Ed1'  , 'active':ED['EdgeDOF'][0]   in ['t','T'], 'q0': ED['IPDefl']   , 'qd0':0 , 'q_channel':'Q_B1E1_[m]', 'qd_channel':'QD_B1E1_[m/s]'}]

# ---------------------- DEGREES OF FREEDOM --------------------------------------
# False          FlapDOF1    - First flapwise blade mode DOF (flag)
# False          FlapDOF2    - Second flapwise blade mode DOF (flag)
# False          EdgeDOF     - First edgewise blade mode DOF (flag)
# ---------------------- INITIAL CONDITIONS --------------------------------------
#           0   OoPDefl     - Initial out-of-plane blade-tip displacement (meters)
#           0   IPDefl      - Initial in-plane blade-tip deflection (meters)


    # --- Return
    WT = WindTurbineStructure()
    WT.hub = hub # origin at S
    WT.gen = gen # origin at S
    WT.nac = nac # origin at N
    WT.twr = twr # origin at T
    WT.fnd = fnd # origin at T
    WT.bld = bld # origin at R
    WT.rot = rot # origin at R, rigid body bld+hub
    WT.RNA = RNA # origin at N, rigid body bld+hub+gen+nac

    WT.DOF= DOFs

    #WT.r_ET_inE = 
    #WT.r_TN_inT
    WT.r_NS_inN = r_NS_inN
    WT.r_NR_inN = r_NR_inN
    WT.r_SR_inS = r_SR_inS
    WT.ED=ED

    return WT


if __name__ == '__main__':
    np.set_printoptions(linewidth=300, precision=2)
    FASTWindTurbine('../../data/NREL5MW/Main_Onshore_OF2.fst')