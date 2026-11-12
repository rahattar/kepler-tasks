#!/bin/bash
# Reference run. Meant for the engineer's container, as the engineer:
#   reads   the turnaround's records under /app/data
#   orders  the six laser visits, once, with the installed laservisit command
#   leaves  the sheet of moves at /app/output/moves.csv
here="$(cd "$(dirname "$0")" && pwd)"
python3 "$here/solve.py" || exit 1
test -s /app/output/moves.csv
