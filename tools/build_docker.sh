#!/bin/bash

set -e
set -u
set -o pipefail

ver=$1
labelversion=$2
tmpdir=$(mktemp -d)

git clone git@github.com:pndni/TNT_pipeline_2.git $tmpdir
pushd $tmpdir

git checkout $ver

lv=""
if [ $labelversion == 1 ]
then
    lv="--label org.opencontainers.image.version=$ver"
fi

docker build --label org.opencontainers.image.revision=$ver --label org.opencontainers.image.created="$(date --rfc-3339=seconds)" $lv -t localhost:5000/tnt_pipeline_2:$ver .

popd
rm -rf $tmpdir
