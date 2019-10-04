#!/bin/bash

set -e
set -u
set -o pipefail

ver=$1
tmpdir=$(mktemp -d)

git clone git@github.com:pndni/TNT_pipeline_2.git $tmpdir
pushd $tmpdir

git checkout $ver
docker build -t localhost:5000/tnt_pipeline_2:$ver . --label org.label-schema.vcs-ref=$ver --label org.label-schema.build-data=$(date --rfc-3339=seconds)

popd
rm -rf $tmpdir
