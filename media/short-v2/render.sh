#!/bin/sh
# Render one edit and master its loudness for YouTube (-14 LUFS, -1 dBTP).
#   ./render.sh [Short|Scope|Cine|Story]      -> out/<id>.mp4
set -e
cd "$(dirname "$0")"
ID=${1:-Short}
# capped: a full render alongside Blender ran the machine out of memory (see tools/capped)
MEM=${MEM:-6G} ../../tools/capped npx remotion render src/index.ts $ID out/raw-$ID.mp4 --log=error --concurrency=${CONC:-4} --crf=16
ffmpeg -v error -y -i out/raw-$ID.mp4 -c:v copy -af "loudnorm=I=-14:TP=-1:LRA=9" -ar 48000 -c:a aac -b:a 256k -movflags +faststart out/$ID.mp4
ffmpeg -i out/$ID.mp4 -af ebur128=peak=true -f null - 2>&1 | grep -A12 Summary | grep -E "I:"
