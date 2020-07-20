"""Read/Write TurbSim File

Part of weio library: https://github.com/ebranlard/weio

"""
import pandas as pd
import numpy as np
import os
import struct
import time

try:
    from .File import File, EmptyFileError
except:
    EmptyFileError = type('EmptyFileError', (Exception,),{})
    File=dict

class TurbSimFile(File):

    @staticmethod
    def defaultExtensions():
        return ['.bts']

    @staticmethod
    def formatName():
        return 'TurbSim binary'

    def __init__(self,filename=None, **kwargs):
        self.filename = None
        if filename:
            self.read(filename, **kwargs)

    def read(self, filename=None, header_only=False):
        """ read BTS file, with field: 
                     u    (3 x nt x ny x nz)
                     uTwr (3 x nt x nTwr)
        """
        if filename:
            self.filename = filename
        if not self.filename:
            raise Exception('No filename provided')
        if not os.path.isfile(self.filename):
            raise OSError(2,'File not found:',self.filename)
        if os.stat(self.filename).st_size == 0:
            raise EmptyFileError('File is empty:',self.filename)

        scl = np.zeros(3, np.float32); off = np.zeros(3, np.float32)
        with open(self.filename, mode='rb') as f:            
            # Reading header info
            ID, nz, ny, nTwr, nt                      = struct.unpack('<h4l', f.read(2+4*4))
            dz, dy, dt, uHub, zHub, zBottom           = struct.unpack('<6f' , f.read(6*4)  )
            scl[0],off[0],scl[1],off[1],scl[2],off[2] = struct.unpack('<6f' , f.read(6*4))
            nChar, = struct.unpack('<l',  f.read(4))
            info = (f.read(nChar)).decode()
            # Reading turbulence field
            if not header_only: 
                u    = np.zeros((3,nt,ny,nz))
                uTwr = np.zeros((3,nt,nTwr))
                # For loop on time (acts as buffer reading, and only possible way when nTwr>0)
                for it in range(nt):
                    Buffer = np.frombuffer(f.read(2*3*ny*nz), dtype=np.int16).astype(np.float32).reshape([3, ny, nz], order='F')
                    u[:,it,:,:]=Buffer
                    Buffer = np.frombuffer(f.read(2*3*nTwr), dtype=np.int16).astype(np.float32).reshape([3, nTwr], order='F')
                    uTwr[:,it,:]=Buffer
                u -= off[:, None, None, None]
                u /= scl[:, None, None, None]
                self['u']    = u
                uTwr -= off[:, None, None]
                uTwr /= scl[:, None, None]
                self['uTwr'] = uTwr
        self['info'] = info
        self['ID']   = ID
        self['dt']   = dt
        self['y']    = np.arange(ny)*dy 
        self['y']   -= np.mean(self['y']) # y always centered on 0
        self['z']    = np.arange(nz)*dz +zBottom
        self['t']    = np.arange(nt)*dt
        self['zTwr'] =-np.arange(nTwr)*dz + zBottom
        self['zHub'] = zHub
        self['uHub'] = uHub

    def write(self, filename=None):
        """ 
        write a BTS file, using the following keys: 'u','z','y','t','uTwr'
                     u    (3 x nt x ny x nz)
                     uTwr (3 x nt x nTwr)
        """
        if filename:
            self.filename = filename
        if not self.filename:
            raise Exception('No filename provided')

        nDim, nt, ny, nz = self['u'].shape
        if 'uTwr' not in self.keys() :
            self['uTwr']=np.zeros((3,nt,0))
        if 'ID' not in self.keys() :
            self['ID']=7

        _, _, nTwr = self['uTwr'].shape
        tsTwr  = self['uTwr']
        ts     = self['u']
        intmin = -32768
        intrng = 65535
        off    = np.empty((3), dtype    = np.float32)
        scl    = np.empty((3), dtype    = np.float32)
        info = 'Generated by TurbSimFile on {:s}.'.format(time.strftime('%d-%b-%Y at %H:%M:%S', time.localtime()))
        # Calculate scaling, offsets and scaling data
        out    = np.empty(ts.shape, dtype=np.int16)
        outTwr = np.empty(tsTwr.shape, dtype=np.int16)
        for k in range(3):
            all_min, all_max = ts[k].min(), ts[k].max()
            if nTwr>0:
                all_min=min(all_min, tsTwr[k].min())
                all_max=max(all_max, tsTwr[k].max())
            if all_min == all_max:
                scl[k] = 1
            else:
                scl[k] = intrng / (all_max-all_min)
            off[k]    = intmin - scl[k] * all_min
            out[k]    = (ts[k]    * scl[k] + off[k]).astype(np.int16)
            outTwr[k] = (tsTwr[k] * scl[k] + off[k]).astype(np.int16)
        z0 = self['z'][0]
        dz = self['z'][1]- self['z'][0]
        dy = self['y'][1]- self['y'][0]
        dt = self['t'][1]- self['t'][0]

        # Providing estimates of uHub and zHub even if these fields are not used
        zHub,uHub, bHub = self.hubValues()

        with open(self.filename, mode='wb') as f:            
            f.write(struct.pack('<h4l', self['ID'], nz, ny, nTwr, nt))
            f.write(struct.pack('<6f', dz, dy, dt, uHub, zHub, z0)) # NOTE uHub, zHub maybe not used
            f.write(struct.pack('<6f', scl[0],off[0],scl[1],off[1],scl[2],off[2]))
            f.write(struct.pack('<l' , len(info)))
            f.write(info.encode())
            for it in np.arange(nt):
                f.write(out[:,it,:,:].tostring(order='F'))
                f.write(outTwr[:,it,:].tostring(order='F'))

    def hubValues(self):
        try:
            zHub=self['zHub']
            bHub=True
        except:
            bHub=False
            iz = np.argmin(np.abs(self['z']-(self['z'][0]+self['z'][-1])/2))
            zHub = self['z'][iz]
        try:
            uHub=self['uHub']
        except:
            iz = np.argmin(np.abs(self['z']-zHub))
            iy = np.argmin(np.abs(self['y']-(self['y'][0]+self['y'][-1])/2))
            uHub = np.mean(self['u'][0,:,iy,iz])
        return zHub, uHub, bHub

    def _iMid(self):
        iy = np.argmin(np.abs(self['y']-(self['y'][0]+self['y'][-1])/2))
        iz = np.argmin(np.abs(self['z']-(self['z'][0]+self['z'][-1])/2))
        return iy,iz

    def makePeriodic(self):
        """ Make the box periodic by mirroring it """
        nDim, nt0, ny, nz = self['u'].shape
        u = self['u'].copy()
        del self['u']

        nt = 2*len(self['t'])-2
        dt = self['t'][1]- self['t'][0]
        self['u']  = np.zeros((nDim,nt,ny,nz))
        self['u'][:,:nt0,:,:] = u
        self['u'][:,nt0:,:,:] = np.flip(u[:,1:-1,:,:],axis=1)
        self['t'] = np.arange(nt)*dt
        if 'uTwr' in self.keys():
            _, _, nTwr = self['uTwr'].shape
            uTwr = self['uTwr'].copy()
            del self['uTwr']
            # empty tower for now
            self['uTwr'] = np.zeros((nDim,nt,nTwr))
            self['uTwr'][:,:nt0,:] = uTwr
            self['uTwr'][:,nt0:,:] = np.flip(uTwr[:,1:-1,:],axis=1)

        self['ID']=8 # Periodic


    def checkPeriodic(self, sigmaTol=1.5, aTol=0.5):
        """ Check periodicity in u """
        ic=0
        sig  = np.std(self['u'][ic,:,:,:],axis=0)
        mean = np.mean(self['u'][ic,:,:,:],axis=0)
        u_first= self['u'][ic,0 ,:,:]
        u_last = self['u'][ic,-1,:,:]
        relSig = np.abs(u_first-u_last)/sig
        compPeriodic = (np.max(relSig) < sigmaTol) and (np.mean(np.abs(u_first-u_last))<aTol)
        return compPeriodic


    def __repr__(self):
        s='<TurbSimFile object> with keys:\n'
        s+=' - ID {}\n'.format(self['ID'])
        s+=' - z: [{} ... {}],  dz: {}, n: {} \n'.format(self['z'][0],self['z'][-1],self['z'][1]-self['z'][0],len(self['z']))
        s+=' - y: [{} ... {}],  dy: {}, n: {} \n'.format(self['y'][0],self['y'][-1],self['y'][1]-self['y'][0],len(self['y']))
        s+=' - t: [{} ... {}],  dt: {}, n: {} \n'.format(self['t'][0],self['t'][-1],self['t'][1]-self['t'][0],len(self['t']))
        s+=' - u: ({} x {} x {} x {}) \n'.format(*(self['u'].shape))
        ux,uy,uz=self['u'][0], self['u'][1], self['u'][2]
        s+='    ux: min: {}, max: {}, mean: {} \n'.format(np.min(ux), np.max(ux), np.mean(ux))
        s+='    uy: min: {}, max: {}, mean: {} \n'.format(np.min(uy), np.max(uy), np.mean(uy))
        s+='    uz: min: {}, max: {}, mean: {} \n'.format(np.min(uz), np.max(uz), np.mean(uz))

        # Mid of box, nearest neighbor
        iy,iz = self._iMid()
        zMid=self['z'][iz]
        yMid=self['y'][iy]
        uMid = np.mean(self['u'][0,:,iy,iz])
        s+='    yMid: {} - zMid: {} - iy: {} - iz: {} - uMid: {} (nearest neighbor))\n'.format(yMid, zMid, iy, iz, uMid)

#         zMid, uMid, bHub = self.hubValues()
#         if bHub:
#             s+='    z"Hub": {} - u"Hub": {} (NOTE: values at TurbSim "hub")\n'.format(zMid, uMid)

        # Tower
        if 'zTwr' in self.keys() and len(self['zTwr'])>0:
            s+=' - zTwr: [{} ... {}],  dz: {}, n: {} \n'.format(self['zTwr'][0],self['zTwr'][-1],self['zTwr'][1]-self['zTwr'][0],len(self['zTwr']))
        if 'uTwr' in self.keys() and self['uTwr'].shape[2]>0:
            s+=' - uTwr: ({} x {} x {} ) \n'.format(*(self['uTwr'].shape))
            ux,uy,uz=self['uTwr'][0], self['uTwr'][1], self['uTwr'][2]
            s+='    ux: min: {}, max: {}, mean: {} \n'.format(np.min(ux), np.max(ux), np.mean(ux))
            s+='    uy: min: {}, max: {}, mean: {} \n'.format(np.min(uy), np.max(uy), np.mean(uy))
            s+='    uz: min: {}, max: {}, mean: {} \n'.format(np.min(uz), np.max(uz), np.mean(uz))
            
        return s

    def toDataFrame(self):
        dfs={}

        ny = len(self['y'])
        nz = len(self['y'])
        # Index at mid box
        iy,iz = self._iMid()

        # Mean vertical profile
        m = np.mean(self['u'][:,:,iy,:], axis=1)
        s = np.std( self['u'][:,:,iy,:], axis=1)
        ti = s/m*100
        Cols=['z_[m]','u_[m/s]','v_[m/s]','w_[m/s]','sigma_u_[m/s]','sigma_v_[m/s]','sigma_w_[m/s]','TI_[%]']
        data = np.column_stack((self['z'],m[0,:],m[1,:],m[2,:],s[0,:],s[1,:],s[2,:],ti[0,:]))
        dfs['VertProfile'] = pd.DataFrame(data = data ,columns = Cols)

        # Mid time series
        u = self['u'][:,:,iy,iz]
        Cols=['t_[s]','u_[m/s]','v_[m/s]','w_[m/s]']
        data = np.column_stack((self['t'],u[0,:],u[1,:],u[2,:]))
        dfs['MidLine'] = pd.DataFrame(data = data ,columns = Cols)

        # Hub time series
        #try:
        #    zHub = self['zHub']
        #    iz = np.argmin(np.abs(self['z']-zHub))
        #    u = self['u'][:,:,iy,iz]
        #    Cols=['t_[s]','u_[m/s]','v_[m/s]','w_[m/s]']
        #    data = np.column_stack((self['t'],u[0,:],u[1,:],u[2,:]))
        #    dfs['TSHubLine'] = pd.DataFrame(data = data ,columns = Cols)
        #except:
        #    pass
        return dfs

if __name__=='__main__':
    ts = TurbSimFile('../_tests/TurbSim.bts')
