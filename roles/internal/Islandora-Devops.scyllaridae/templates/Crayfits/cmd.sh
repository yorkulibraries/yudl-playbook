#!/bin/bash
TMPFILE=$(mktemp)
trap "rm -f $TMPFILE" EXIT
cat > "$TMPFILE"
curl -X POST -F "datafile=@${TMPFILE}" http://localhost:8080/fits/examine
