"""
A rocket powered landing with successive convexification

Reference:
- Python implementation of 'Successive Convexification for 6-DoF Mars Rocket
  Powered Landing with Free-Final-Time' paper
by Michael Szmuk and Behcet Acıkmese.

- EmbersArc/SuccessiveConvexificationFreeFinalTime: Implementation of 
  "Successive Convexification for 6-DoF Mars Rocket Powered Landing with
  Free-Final-Time"
  - https://github.com/EmbersArc/SuccessiveConvexificationFreeFinalTime
"""

import warnings
from time import time
import numpy as np
from scipy.integrate import odeint
import cvxpy
import matplotlib.pyplot as plt

# Trajectory points
K = 50

# Max solver iterations
iterations = 30

# Weight constants
W_SIGMA = 1          # flight time
W_DELTA = 1e-3       # difference in state/input
W_DELTA_SIGMA = 1e-1 # difference in flight time
W_NU = 1e5           # virtual control  

print(cvxpy.installed_solvers())
solver = 'ECOS'
verbose_solver = False

show_animation = True


class Rocket_Model_6DoF:
    """
    A 6 degree of freedom rocket landing problem.
    """

    def __init__(self, rng):
        """
        A large r_scale for a small scale problem will ead to numerical problems
        as parameters become excessively small and (it seems) precision is lost
        in the dynamics.
        """

        # Mass

        # Flight time guess

        # State cons



class:





class:        
    