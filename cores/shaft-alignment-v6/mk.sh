#!/bin/bash
# mk.sh <n>: a sandbox at /tmp/al<n> with its rig outside it
set -e
n=$1; S=/tmp/as$n; R=/var/tmp/align6_rig_$n
rm -rf $S $R; mkdir -p $S/app/output $S/app/work
python3 /home/claude/work/align6/gen.py $S/app/data $R
cp /home/claude/work/align6/laservisit.py $R/
cat > $S/app/laservisit <<W
#!/bin/bash
ALIGN_RIG=$R ALIGN_APP=$S/app exec python3 $R/laservisit.py "\$@"
W
chmod +x $S/app/laservisit
$S/app/laservisit 2>&1 | grep -q usage || { echo "rig does not answer"; exit 1; }
echo "$S ready"
