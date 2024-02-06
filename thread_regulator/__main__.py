import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from thread_regulator.graphs import drag_drop_dashboard as ddd

if __name__ == "__main__":
    ddd.start_dash()
