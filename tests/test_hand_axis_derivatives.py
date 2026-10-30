"""Independent differential checks of exported joint axes and coordinate rank."""
from pathlib import Path
import sys
import unittest
try:
    import numpy as np
except ImportError as error:
    raise unittest.SkipTest('Optional NumPy/CAD runtime unavailable') from error

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/frcstack/scripts'))
import hand_kinematics as hk


class AxisDerivativeTests(unittest.TestCase):
    def test_all_reported_axes_match_independent_rotation_derivatives(self):
        angles=hk.pose('partial')
        base=hk.forward_kinematics(angles)
        step_deg=1e-4; step_rad=np.deg2rad(step_deg)
        for spec in hk.joint_specs():
            with self.subTest(joint=spec['name']):
                q=dict(angles);q[spec['name']]+=step_deg
                changed=hk.forward_kinematics(q)
                before=base['links'][spec['child_link']]
                after=changed['links'][spec['child_link']]
                delta=(after[:3,:3]@before[:3,:3].T-np.eye(3))/step_rad
                angular=np.array([delta[2,1]-delta[1,2],delta[0,2]-delta[2,0],delta[1,0]-delta[0,1]])/2
                np.testing.assert_allclose(angular,base['joints'][spec['name']]['axis_world'],atol=1e-7)
                np.testing.assert_allclose(after[:3,3],before[:3,3],atol=1e-9)

    def test_full_link_configuration_has_twenty_independent_coordinates(self):
        angles=hk.pose('partial')
        base=hk.forward_kinematics(angles)
        moving=[s['child_link'] for s in hk.joint_specs()]
        def flatten(model):
            return np.concatenate([model['links'][n][:3,:].reshape(-1) for n in moving])
        baseline=flatten(base);columns=[]
        for spec in hk.joint_specs():
            q=dict(angles);q[spec['name']]+=1e-4
            columns.append((flatten(hk.forward_kinematics(q))-baseline)/np.deg2rad(1e-4))
        jacobian=np.column_stack(columns)
        self.assertEqual(np.linalg.matrix_rank(jacobian,tol=1e-6),20)
        # This is configuration-coordinate independence, not tendon controllability.


if __name__=='__main__':
    unittest.main()
