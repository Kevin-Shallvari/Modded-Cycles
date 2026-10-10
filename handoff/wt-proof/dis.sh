#!/bin/sh
# dis.sh start stop
m68k-elf-objdump -D -b binary -m m68k:cfv4e --adjust-vma=0x40000400 --start-address=$1 --stop-address=$2 /home/kevin/Desktop/repos/Modded-Cycles/build/wt-proof/mainos.bin | tail -n +8
