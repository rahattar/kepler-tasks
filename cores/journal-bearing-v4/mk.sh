#!/bin/bash
# mk.sh <n>: a probe sandbox at /tmp/jf<n>
set -e
n=$1; S=/tmp/jf$n
rm -rf $S; mkdir -p $S/app/output $S/app/work
cp -r /home/claude/work/jb4/core/data $S/app/data
cp -r /home/claude/work/jb4/core/tools $S/app/tools
sed "s#PROBE#$S#g" /home/claude/work/jb4/brief.txt > $S/brief.txt
echo "$S ready"
