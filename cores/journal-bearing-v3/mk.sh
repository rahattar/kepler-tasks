#!/bin/bash
# mk.sh <n>: a probe sandbox at /tmp/je<n>
set -e
n=$1; S=/tmp/je$n
rm -rf $S; mkdir -p $S/app/output $S/app/work
cp -r /home/claude/work/jb3/core/data $S/app/data
sed "s#PROBE#$S#g" /home/claude/work/jb3/brief.txt > $S/brief.txt
echo "$S ready"
