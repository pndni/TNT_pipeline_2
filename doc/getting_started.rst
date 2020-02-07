Getting Started
---------------

Singularity
^^^^^^^^^^^

The easiest way to get started is to install using singularity

.. code-block:: bash

    singularity build $name docker://pndni/tnt_pipeline_2:$ver

where ``$name`` is the name of the saved image, e.g. ``tnt_pipeline_2.sif``, and
``$ver`` is the version.
See `docker hub <https://hub.docker.com/repository/docker/pndni/tnt_pipeline_2>`_
for which tags are available.

Basic Usage
^^^^^^^^^^^

This assumes you are in a directory with the singularity image ``tnt_pipeline_2.sif``,
a bids directory ``bids``, and output directory ``out``.
The basic usage is

.. code-block:: bash

   singularity run --cleanenv --no-home tnt_pipeline_2.sif bids out participant

To include intracranial volume and subcortical structures

.. code-block:: bash

   singularity run --cleanenv --no-home tnt_pipeline_2.sif bids out participant \
   --intracranial_volume \
   --subcortical

The default model is SYS808. If a different model is needed, then you'll need to specify some additional information.
For example, to use an MNI model

.. code-block:: bash

   singularity run --cleanenv --no-home tnt_pipeline_2.sif bids out participant \
   --intracranial_volume \
   --subcortical \
    --model_space ICBM152NlinSymIV \
    --model models/icbm_avg_152_t1_tal_nlin_symmetric_VI.nii \
    --atlas models/atlas_labels_nomiddle_rs.nii \
    --tags models/ntags_1000_prob_90_nobg.tsv \
    --model_brain_mask models/icbm_avg_152_t1_tal_nlin_symmetric_VI_mask.nii \
    --intracranial_mask models/icbm_ICVmask_tp2013.nii

Where ``--model_space`` is just a name you choose, ``--model`` is the actual model brain,
``--atlas`` labels each ROI on the model (e.g., lobes), ``--tags`` is a list of points
and their classification to train the classifier, ``--model_brain_mask`` is a mask
of the brain in model space, and ``--intracranial_mask`` is used to calculate intracranial volume.
This assumes that a file labeling the atlas ROIs named ``--models/icbm_avg_152_t1_tal_nlin_symmetric_VI_labels.tsv``
exists and a file labeling the tags named ``--models/ntags_1000_prob_90_nobg_labels.tsv`` exists. This can be
overridden with ``--atlas_labels`` and ``--tag_labels``, respectively. See :doc:`command_line_usage` for more information.
