#!/usr/bin/env python3
import os
import sys

try:
    ipaddr = sys.argv[1]
except IndexError:
    print("Usage: python con_noprompt.py <ipaddr of conqr server>")
    sys.exit()

# Prefer launching from the conference folder root.
conqr_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "conqr.py")
if not os.path.isfile(conqr_path):
    conqr_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conqr.py")

os.chdir(os.path.dirname(conqr_path))
os.execv(sys.executable, [sys.executable, conqr_path, "4", ipaddr])
