# AIACE GeoMathUtil.py V.0.71a
from functools import lru_cache

import numpy as np
import numpy.linalg as la

D2R = np.pi/180.0
R2D = 180.0/np.pi


# ponytail: retain only recent geometry; byte keys capture mutable arrays and their precision.
@lru_cache(maxsize=128)
def _body_los(pose_dtype, pose_bytes, target_dtype, target_bytes, proj):
    pose = np.frombuffer(pose_bytes, dtype=pose_dtype)
    target_position = np.frombuffer(target_bytes, dtype=target_dtype)
    roll, pitch, heading = np.asarray(pose[3:6])*D2R
    Tz = np.array([[np.cos(heading), np.sin(heading), 0],
                   [-np.sin(heading), np.cos(heading), 0], [0, 0, 1]])
    p_ned = np.asarray(target_position) - np.asarray(pose[:3])
    distance = la.norm(p_ned)
    p_unit = p_ned / distance if distance != 0 else p_ned
    if proj:
        return tuple(np.matmul(Tz, p_unit))
    Tx = np.array([[1, 0, 0], [0, np.cos(roll), np.sin(roll)],
                   [0, -np.sin(roll), np.cos(roll)]])
    Ty = np.array([[np.cos(pitch), 0, -np.sin(pitch)], [0, 1, 0],
                   [np.sin(pitch), 0, np.cos(pitch)]])
    return tuple(np.matmul(np.matmul(Tx, np.matmul(Ty, Tz)), p_unit))


class GeometryInfo():
    def __init__(self):
        pass
    
    def get_geometry_info_ned(self, ownship_ned:np.array, target_ned:np.array):
        dis = self._get_distance(ownship_ned, target_ned)
        aa  = self._get_aspect_angle(ownship_ned, target_ned, proj=False)
        hca = self._get_heading_cross_angle(ownship_ned, target_ned, proj=False)
        ata = self._get_antenna_train_angle(ownship_ned, target_ned, proj=False)

        return dis, aa, hca, ata 

    def _get_distance(self, ownship_ned, target_ned):
        pos_vec = target_ned[0:3] - ownship_ned[0:3]
        _distance = la.norm(pos_vec)

        return _distance

    def _get_down_angle(self, ownship_rpy):
        _angle = 0
        roll, pitch, heading = ownship_rpy[0]*D2R, ownship_rpy[1]*D2R, ownship_rpy[2]*D2R
        Tx = np.array([[1, 0, 0], [0, np.cos(roll), np.sin(roll)], [0, -np.sin(roll), np.cos(roll)]])
        Ty = np.array([[np.cos(pitch), 0, -np.sin(pitch)], [0, 1, 0], [np.sin(pitch), 0, np.cos(pitch)]])
        Tz = np.array([[np.cos(heading), np.sin(heading), 0], [-np.sin(heading), np.cos(heading), 0], [0, 0, 1]])

        T = np.matmul(np.matmul(Tx, np.matmul(Ty, Tz)), [0, 0, -1])
        _angle = np.arccos(np.clip(T[0], -1.0, 1.0))*R2D

        return _angle


    def _get_aspect_angle(self, ownship_ned, target_ned, proj=False):
        x, y, z = _body_los(target_ned.dtype.str, target_ned[:6].tobytes(),
                            ownship_ned.dtype.str, ownship_ned[:3].tobytes(), proj)
        # Tz_pi reverses the forward/right axes, preserving the historical AA convention.
        # Matrix multiplication sums zero components to +0 (atan2 distinguishes -0).
        p_unit_t = (0.0 if x == 0 else -x, 0.0 if y == 0 else -y, z)
        
        # 2D ATA
        if (proj == True):
            _angle = np.arctan2(p_unit_t[1], p_unit_t[0])*R2D
        # 3D ATA
        else:
            # 3D에서는 부호가 정의가 안되서... 아래는 수정이 필요할 수 있다.
            sign = 1
            if p_unit_t[1] < -0.10:
                sign = -1
            elif -0.01 < p_unit_t[1] < 0.01:
                sign = np.sign(p_unit_t[2])
            _angle = sign*np.arccos(np.clip(p_unit_t[0],-1.0,1.0))*R2D

        return _angle

    def _get_heading_cross_angle(self, ownship_ned, target_ned, proj=False):
        _angle = 0
        # target
        roll, pitch, heading = target_ned[3]*D2R, target_ned[4]*D2R, target_ned[5]*D2R
        Rx = np.array([[1, 0, 0], [0, np.cos(roll), -np.sin(roll)], [0, np.sin(roll), np.cos(roll)]])
        Ry = np.array([[np.cos(pitch), 0, np.sin(pitch)], [0, 1, 0], [-np.sin(pitch), 0, np.cos(pitch)]])
        Rz = np.array([[np.cos(heading), -np.sin(heading), 0], [np.sin(heading), np.cos(heading), 0], [0, 0, 1]])

        roll, pitch, heading = ownship_ned[3]*D2R, ownship_ned[4]*D2R, ownship_ned[5]*D2R
        Tx = np.array([[1, 0, 0], [0, np.cos(roll), np.sin(roll)], [0, -np.sin(roll), np.cos(roll)]])
        Ty = np.array([[np.cos(pitch), 0, -np.sin(pitch)], [0, 1, 0], [np.sin(pitch), 0, np.cos(pitch)]])
        Tz = np.array([[np.cos(heading), np.sin(heading), 0], [-np.sin(heading), np.cos(heading), 0], [0, 0, 1]])
        
        if proj == True:
            V_t = np.matmul(Rz, np.array([1, 0, 0]))
            V_t_body = np.matmul(Tz, V_t)
            _angle = np.arctan2(V_t_body[1], V_t_body[0])*R2D
        else:
            V_t = np.matmul(Rz, np.matmul(Ry, np.matmul(Rx, np.array([1, 0, 0]))))
            V_t_body = np.matmul(Tx, np.matmul(Ty, np.matmul(Tz, V_t)))
            # 3D에서는 부호가 정의가 안되서... 아래는 수정이 필요할 수 있다.
            sign = 1
            if V_t_body[1] < -0.10:
                sign = -1
            elif -0.01 < V_t_body[1] < 0.01:
                sign = np.sign(V_t_body[2])
            _angle = sign*np.arccos(np.clip(V_t_body[0],-1.0,1.0))*R2D

        return _angle


    def _get_antenna_train_angle(self, ownship_ned, target_ned, proj = False):
        p_unit_t = _body_los(ownship_ned.dtype.str, ownship_ned[:6].tobytes(),
                             target_ned.dtype.str, target_ned[:3].tobytes(), proj)
        
        # 2D ATA
        if (proj == True):
            _angle = np.arctan2(p_unit_t[1], p_unit_t[0])*R2D
        # 3D ATA
        else:
            _angle = np.arccos(np.clip(p_unit_t[0], -1.0, 1.0))*R2D

        return _angle


    def _get_los_angle(self, ownship_ned, target_ned):
        dis_body_norm = _body_los(ownship_ned.dtype.str, ownship_ned[:6].tobytes(),
                                 target_ned.dtype.str, target_ned[:3].tobytes(), False)
        
        _az = np.arctan2(dis_body_norm[1], dis_body_norm[0])*R2D  # -180 ~ 180
        _el = -np.arcsin(np.clip(dis_body_norm[2], -1.0, 1.0))*R2D  # -90 ~ 90
        
        return _az, _el
