# Import required library
import subprocess
import re

def check_ethernet_speed():
    """
    Check ethernet interface maximum speed capability using ethtool
    Prints the max speed capacity of each ethernet interface
    """
    try:
        # First get list of ethernet interfaces
        # Use ip link to list interfaces
        interfaces = subprocess.check_output(['ip', 'link', 'show'], text=True)
        
        # Find ethernet interfaces (usually start with 'eth' or 'enp')
        ethernet_interfaces = re.findall(r'[0-9]+: (e[a-zA-Z0-9]+):', interfaces)
        
        print("\nChecking Ethernet Interface Speeds:")
        print("-" * 50)
        
        for interface in ethernet_interfaces:
            try:
                # Run ethtool command for each interface
                ethtool_output = subprocess.check_output(['ethtool', interface], text=True)
                
                # Look for Speed line in output
                speed_line = re.search(r'Speed: ([0-9]+[A-Za-z]+/s)', ethtool_output)
                
                if speed_line:
                    print(f"Interface {interface}: {speed_line.group(1)}")
                else:
                    print(f"Interface {interface}: Speed not detected")
                    
            except subprocess.CalledProcessError:
                print(f"Interface {interface}: Could not read speed (try running with sudo)")
                
    except subprocess.CalledProcessError:
        print("Error: Could not get interface list (try running with sudo)")
    except FileNotFoundError:
        print("Error: ethtool not found. Please install it:")
        print("Ubuntu/Debian: sudo apt-get install ethtool")
        print("RHEL/CentOS: sudo yum install ethtool")
        print("Arch: sudo pacman -S ethtool")

# Run the check
if __name__ == "__main__":
    check_ethernet_speed()
    print("\nNote: For accurate results, run with sudo:")
    print("sudo python3 ethernet_speed.py")
