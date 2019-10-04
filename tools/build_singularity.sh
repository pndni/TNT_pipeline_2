#!/bin/bash

set -e
set -u
set -o pipefail

ver=$1

outfile=TNT_pipeline_2-${ver}.simg

if [ -e $outfile ]
then
    >&2 echo "$outfile already exists"
    exit 1
fi

export SINGULARITY_NOHTTPS=1
export SINGULARITY_TMPDIR=$(mktemp -d -p ~/tmp)
singularity build $outfile docker://localhost:5000/tnt_pipeline_2:$ver
