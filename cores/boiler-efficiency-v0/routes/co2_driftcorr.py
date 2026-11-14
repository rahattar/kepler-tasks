import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import efficiency as e
e.EA_SOURCE, e.IDENT = 'co2corr', 'median'
e.main(sys.argv[1], sys.argv[2])
