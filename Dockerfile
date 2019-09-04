FROM centos:7.6.1810


RUN yum install -y epel-release && \
    yum install -y wget file bc tar gzip libquadmath which bzip2 libgomp tcsh perl less zlib zlib-devel hostname && \
    yum groupinstall -y "Development Tools" && \
    wget https://github.com/Kitware/CMake/releases/download/v3.14.0/cmake-3.14.0-Linux-x86_64.sh && \
    mkdir -p /opt/cmake && \
    /bin/bash cmake-3.14.0-Linux-x86_64.sh --prefix=/opt/cmake --skip-license && \
    rm cmake-3.14.0-Linux-x86_64.sh
ENV PATH /opt/cmake/bin:$PATH

# ANTs
RUN tmpdir=$(mktemp -d) && \
    pushd $tmpdir && \
    git clone --branch v2.3.1 https://github.com/ANTsX/ANTs.git ANTs_src && \
    mkdir ANTs_build && \
    pushd ANTs_build && \
    cmake ../ANTs_src -DITK_BUILD_MINC_SUPPORT=ON -DCMAKE_BUILD_TYPE=RELEASE && \
    make -j 2 && \
    popd && \
    mkdir -p /opt/ants/bin && \
    cp ANTs_src/Scripts/* /opt/ants/bin/ && \
    cp ANTs_build/bin/* /opt/ants/bin/ && \
    popd && \
    rm -rf $tmpdir


# MINC
RUN tmpdir=$(mktemp -d) && \
    pushd $tmpdir && \
    git clone --recursive --branch release-1.9.17 https://github.com/BIC-MNI/minc-toolkit-v2.git minc-toolkit-v2_src && \
    mkdir minc_build && \
    pushd minc_build && \
    cmake ../minc-toolkit-v2_src \
    -DCMAKE_BUILD_TYPE:STRING=Release \
    -DCMAKE_INSTALL_PREFIX:PATH=/opt/minc \
    -DMT_BUILD_ABC:BOOL=OFF \
    -DMT_BUILD_ANTS:BOOL=OFF \
    -DMT_BUILD_C3D:BOOL=OFF \
    -DMT_BUILD_ELASTIX:BOOL=OFF \
    -DMT_BUILD_IM:BOOL=OFF \
    -DMT_BUILD_ITK_TOOLS:BOOL=OFF \
    -DMT_BUILD_LITE:BOOL=OFF \
    -DMT_BUILD_OPENBLAS:BOOL=ON \
    -DMT_BUILD_QUIET:BOOL=OFF \
    -DMT_BUILD_SHARED_LIBS:BOOL=OFF \
    -DMT_BUILD_VISUAL_TOOLS:BOOL=OFF \
    -DMT_USE_OPENMP:BOOL=ON \
    -DUSE_SYSTEM_FFTW3D:BOOL=OFF \
    -DUSE_SYSTEM_FFTW3F:BOOL=OFF \
    -DUSE_SYSTEM_GLUT:BOOL=OFF \
    -DUSE_SYSTEM_GSL:BOOL=OFF \
    -DUSE_SYSTEM_HDF5:BOOL=OFF \
    -DUSE_SYSTEM_ITK:BOOL=OFF \
    -DUSE_SYSTEM_NETCDF:BOOL=OFF \
    -DUSE_SYSTEM_NIFTI:BOOL=OFF \
    -DUSE_SYSTEM_PCRE:BOOL=OFF \
    -DUSE_SYSTEM_ZLIB:BOOL=OFF \
    -DBUILD_TESTING=ON && \
    make && \
    make test && \
    make install && \
    popd && \
    rm -rf minc_build && \
    rm -rf minc-toolkit-v2_src && \
    popd


# FSL
RUN wget --output-document=/root/fslinstaller.py https://fsl.fmrib.ox.ac.uk/fsldownloads/fslinstaller.py  && \
    python /root/fslinstaller.py -p -V 6.0.1 -d /opt/fsl && \
    rm /root/fslinstaller.py

# python
RUN yum install -y python36 python36-pip python36-devel libstdc++-static && \
    pip3.6 --no-cache-dir install numpy==1.16.3 bids-validator==1.2.4 pybids==0.9.2 nibabel==2.4.0 duecredit==0.7.0 \
    git+https://github.com/stilley2/nipype.git@ac54739effc8fdd7d89a57b5aac91b3f7cefd760 \
    git+https://github.com/pndni/pndni_utils.git@62e71a3ef8f52b70a83bc4f04e5e83583ec8b86f \
    git+https://github.com/pndni/pndniworkflows.git@5683bb0ca3fe6d90f4d53c6fe06c30c1212c62f0

ENV ANTSPATH=/opt/ants/bin PATH=/opt/ants/bin:$PATH
ENV FSLDIR=/opt/fsl \
    FSLOUTPUTTYPE="NIFTI_GZ" \
    FSLMULTIFILEQUIT="TRUE" \
    FSLTCLSH="/opt/fsl/bin/fsltclsh" \
    FSLWISH="/opt/fsl/bin/fslwish" \
    FSLLOCKDIR="" \
    FSLMACHINELIST="" \
    FSLREMOTECALL="" \
    FSLGECUDAQ="cuda.q" \
    PATH=/opt/fsl/bin:$PATH

ENV MINC_TOOLKIT=/opt/minc \
    MINC_TOOLKIT_VERSION="1.9.17-20190313" \
    PATH=/opt/minc/bin:/opt/minc/pipeline:$PATH \
    PERL5LIB=/opt/minc/perl:/opt/minc/pipeline:$PERL5LIB \
    MNI_DATAPATH=/opt/share \
    MINC_FORCE_V2="1" \
    MINC_COMPRESS="4" \
    VOLUME_CACHE_THRESHOLD="-1"

COPY template /template
COPY setup.py /opt/TNT_pipeline_2/
COPY TNT_pipeline_2 /opt/TNT_pipeline_2/TNT_pipeline_2
RUN pip3.6 install -e /opt/TNT_pipeline_2/
ENTRYPOINT ["TNT_pipeline_2"]