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
