#!/bin/bash
# mk.sh <n>: a probe sandbox at /tmp/jc<n>
set -e
n=$1; S=/tmp/jc$n
rm -rf $S; mkdir -p $S/app/output $S/app/work
cp -r /home/claude/work/jb1/core/data $S/app/data
sed "s#PROBE#$S#g" /home/claude/work/jb1/brief.txt > $S/brief.txt
echo "$S ready"
