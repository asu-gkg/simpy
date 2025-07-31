#!/usr/bin/env python3
"""
Test script to compare Python and C++ MPTCP simulation outputs
"""

import subprocess
import os
import sys
import time

def run_simulation(implementation, args):
    """Run either Python or C++ simulation"""
    if implementation == "python":
        cmd = ["uv", "run", "python", "network_frontend/htsimpy/examples/05_mptcp_example/main.py"] + args
        cwd = "/Users/nancy/PycharmProjects/simpy"
    else:  # C++
        cmd = ["./main"] + args
        cwd = "/Users/nancy/PycharmProjects/simpy/csg-htsim/sim/tests"
    
    print(f"\nRunning {implementation} simulation...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error running {implementation}:")
            print(result.stderr)
            return None
        return result.stdout
    except Exception as e:
        print(f"Exception running {implementation}: {e}")
        return None

def compare_log_files(file1, file2):
    """Compare two log files"""
    print(f"\nComparing log files:")
    print(f"File 1: {file1}")
    print(f"File 2: {file2}")
    
    if not os.path.exists(file1):
        print(f"File 1 does not exist: {file1}")
        return
    
    if not os.path.exists(file2):
        print(f"File 2 does not exist: {file2}")
        return
    
    # Get file sizes
    size1 = os.path.getsize(file1)
    size2 = os.path.getsize(file2)
    print(f"File 1 size: {size1} bytes")
    print(f"File 2 size: {size2} bytes")
    
    # Read first few lines
    with open(file1, 'rb') as f:
        lines1 = f.readlines()[:30]
    
    with open(file2, 'rb') as f:
        lines2 = f.readlines()[:30]
    
    print(f"\nFirst 30 lines comparison:")
    print(f"File 1 has {len(lines1)} lines")
    print(f"File 2 has {len(lines2)} lines")
    
    # Compare line by line
    for i, (line1, line2) in enumerate(zip(lines1, lines2)):
        if line1 != line2:
            print(f"Difference at line {i+1}:")
            print(f"  File 1: {line1}")
            print(f"  File 2: {line2}")

def main():
    # Test parameters
    test_cases = [
        ["UNCOUPLED", "400", "10000", "3000", "2"],
        # ["COUPLED_INC", "400", "10000", "3000", "2"],
        # ["FULLY_COUPLED", "400", "10000", "3000", "2"],
    ]
    
    for args in test_cases:
        print("\n" + "="*60)
        print(f"Test case: {' '.join(args)}")
        print("="*60)
        
        # Run Python version
        py_output = run_simulation("python", args)
        
        # Wait a bit to ensure file is written
        time.sleep(1)
        
        # Run C++ version
        cpp_output = run_simulation("cpp", args)
        
        # Wait a bit to ensure file is written
        time.sleep(1)
        
        # Compare outputs
        if py_output and cpp_output:
            print("\n--- Python output summary ---")
            py_lines = py_output.strip().split('\n')
            for line in py_lines[-10:]:
                print(line)
            
            print("\n--- C++ output summary ---")
            cpp_lines = cpp_output.strip().split('\n')
            for line in cpp_lines[-10:]:
                print(line)
        
        # Compare log files
        logfile = f"logout.{args[1]}pktps.{int(args[2])}ms.{args[3]}rwnd"
        py_logfile = f"/Users/nancy/PycharmProjects/simpy/data/{logfile}"
        cpp_logfile = f"/Users/nancy/PycharmProjects/simpy/csg-htsim/sim/data/{logfile}"
        
        compare_log_files(py_logfile, cpp_logfile)

if __name__ == "__main__":
    main()