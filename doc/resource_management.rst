Resource Management
-------------------

ANTs processor usage
^^^^^^^^^^^^^^^^^^^^

The biggest bottleneck in this pipeline is ANTs. Therefore,
an important argument is ``--ants_n_proc``, which sets how
many processors a given ANTs process can use

Nipype multiproc
^^^^^^^^^^^^^^^^

This pipeline is built on :py:mod:`nipype`, and most usage will use the ``MultiProc``
backend. This packend allows each pipeline step to be assigned an estimated
processor count and memory usage, which the backend uses to distribute resources.
Properly setting this values may improve performance, particularly when more
participants than cores are assigned. This pipeline provides an easy way to do this.

1. Profiling
""""""""""""

The first step is the profile your run using a couple of participants. The run environment
should be identical do the intendended run, save for the number of participants, the ``--profiling_output_file``
parameter and the ``--debug`` parameter. (The debug parameter reduces the number of registration interations.)
You'll probably also want to set the ``--memory_gb`` parameter to tell the pipeline how much memory you have.

.. code-block:: bash

   singularity run --cleanenv --no-home tnt_pipeline_2.sif bids out participant \
   --intracranial_volume \
   --subcortical \
   --debug \
   --memory_gb 188 \
   --profiling_output_file proj.json

2. Converting profiling file
""""""""""""""""""""""""""""

To convert the profiling file to a resources file, run

.. code-block:: bash

    singularity run --cleanenv --no-home TNT_pipeline_2.sif \
    bids out create_resource_file \
    --profiling_input_file prof.json \
    --resource_output_file res.json

3. Run the pipeline with the resource file
""""""""""""""""""""""""""""""""""""""""""

Finally, run the pipeline with the resource file as input

.. code-block:: bash
   
   singularity run --cleanenv --no-home tnt_pipeline_2.sif bids out participant \
   --intracranial_volume \
   --subcortical \
   --memory_gb 188 \
   --resource_input_file res.json
