#!/usr/bin/env bash
#
# volumpdown [volup, voldown]
#   use alsa mixer to incr or decr volume by a quantum depending on argv0
#
# scott@smemsh.net
# https://github.com/smemsh/utilmisc/
# https://spdx.org/licenses/GPL-2.0
#

invname=${0##*/}
quantum=3
volcur=$(amixer get Master scontents | grep % | grep -Po '\d+%')
voldown=0; volup=1
volbool=$((${!invname}))
amixer sset Master $((${volcur%\%} + quantum * (2 * volbool - 1)))%
