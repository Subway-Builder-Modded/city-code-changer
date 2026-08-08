## City Code Changer
This script converts a .metro save file's city code.  This allows you to migrate a network from one map to another if they have overlapping area.  For example, SJU to PR, or LAXM to LAX.

Run the code like so:

    python change_city_code.py <path to .metro file> <new city code>

or, if you make `change_city_code.py` executable:

    ./change_city_code.py <path to input .metro file> <new city code>

Example:

    ./change_city_code.py sju14_24a156bcb1a542b484dd539ba14227c7.metro PR

This produces an output file at the same location as the input .metro file, named `<new city code>_<path to input .metro file>`:

    PR_sju14_24a156bcb1a542b484dd539ba14227c7.metro

You can also use the pre-compiled executables available under Releases.  These are used exactly the same as the `change_city_code.py` file, e.g.,
    ./change_city_code_linux_x86-64.bin sju14_24a156bcb1a542b484dd539ba14227c7.metro PR

Before running it, make sure that you make the file executable:
    chmod +x change_city_code_linux_x86-64.bin

You need to run this in a terminal/shell.  Exact instructions will depend on your operating system, so if you're not sure how to do it, ask AI.

## Setting up a Python environment
You don't need a Python environment to use one of the pre-compiled executables available under Releases.

But, if you want to run it via Python, I'm being lazy and not providing a unique environment for this script.  The packages are readily available and versions shouldn't matter.  It only uses built-in libraries, so any Python install should work.  If you have issues with whatever Python install you have, you can use [Depot's environment file](https://github.com/Subway-Builder-Modded/depot/blob/main/environment.yml) if you want; see installation instructions in the [Depot readme](https://github.com/Subway-Builder-Modded/depot).

## Credit
This code heavily follows [ejfox's metro-savefile-doctor](https://github.com/ejfox/metro-savefile-doctor) to handle the file formatting.  A big thank you to EJ for making that code public!
