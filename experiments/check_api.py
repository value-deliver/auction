#!/usr/bin/env python3
import hcaptcha_challenger

print("hcaptcha-challenger API investigation:")
print("=" * 50)

# Check version
print(f"Version: {getattr(hcaptcha_challenger, '__version__', 'unknown')}")

# Check what's available
print("\nAvailable classes/functions:")
for name in sorted(dir(hcaptcha_challenger)):
    if not name.startswith('_'):
        obj = getattr(hcaptcha_challenger, name)
        print(f"  {name}: {type(obj)}")

# Check for solve methods
print("\nChecking for solve-related methods:")
for name in dir(hcaptcha_challenger):
    obj = getattr(hcaptcha_challenger, name)
    if callable(obj) and ('solve' in name.lower() or 'handle' in name.lower()):
        print(f"  {name}: {obj}")

# Try to understand the main API
print("\nTrying to understand main API...")
try:
    # Check if handle function exists
    if hasattr(hcaptcha_challenger, 'handle'):
        print("handle function found - this might be the main entry point")
        print(f"handle signature: {hcaptcha_challenger.handle.__doc__}")
except Exception as e:
    print(f"Error checking handle: {e}")

# Check for any class that might be the main solver
print("\nChecking for potential solver classes:")
potential_solvers = []
for name in dir(hcaptcha_challenger):
    obj = getattr(hcaptcha_challenger, name)
    if hasattr(obj, '__init__') and hasattr(obj, '__call__'):
        potential_solvers.append(name)

if potential_solvers:
    print(f"Potential solver classes: {potential_solvers}")
else:
    print("No obvious solver classes found")