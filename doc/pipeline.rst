Pipeline Overview
-----------------

.. autofunction:: TNT_pipeline_2.core_workflows.main_workflow

   .. workflow::
      :graph2use: orig
      :simple_form: no

      from TNT_pipeline_2.core_workflows import main_workflow
      wf = main_workflow('', 0.5, 0.0, [0.0, 5000.0], 1.0, subcortical=True, subcort_statslabels='', icv=True)


.. autofunction:: TNT_pipeline_2.core_workflows.preproc_workflow

   .. workflow::
      :graph2use: orig
      :simple_form: no

      from TNT_pipeline_2.core_workflows import preproc_workflow
      wf = preproc_workflow(0.5, 0.0, [0.0, 5000.0], 1.0, 1e-6)


.. autofunction:: TNT_pipeline_2.core_workflows.ants_workflow

   .. workflow::
      :graph2use: orig
      :simple_form: no

      from TNT_pipeline_2.core_workflows import ants_workflow
      wf = ants_workflow()


.. autofunction:: TNT_pipeline_2.core_workflows.classify_workflow

   .. workflow::
      :graph2use: orig
      :simple_form: no

      from TNT_pipeline_2.core_workflows import classify_workflow
      wf = classify_workflow(1e-6)


.. autofunction:: TNT_pipeline_2.core_workflows.segment_lobes_workflow

   .. workflow::
      :graph2use: orig
      :simple_form: no

      from TNT_pipeline_2.core_workflows import segment_lobes_workflow
      wf = segment_lobes_workflow()


.. autofunction:: TNT_pipeline_2.core_workflows.subcortical_workflow

   .. workflow::
      :graph2use: orig
      :simple_form: no

      from TNT_pipeline_2.core_workflows import subcortical_workflow
      wf = subcortical_workflow()


.. autofunction:: TNT_pipeline_2.core_workflows.icv_workflow

   .. workflow::
      :graph2use: orig
      :simple_form: no

      from TNT_pipeline_2.core_workflows import icv_workflow
      wf = icv_workflow()


.. autofunction:: TNT_pipeline_2.core_workflows.tomnc_workflow

   .. workflow::
      :graph2use: orig
      :simple_form: no

      from TNT_pipeline_2.core_workflows import tomnc_workflow
      wf = tomnc_workflow('name')


.. autofunction:: TNT_pipeline_2.core_workflows.toniigz_workflow

   .. workflow::
      :graph2use: orig
      :simple_form: no

      from TNT_pipeline_2.core_workflows import toniigz_workflow
      wf = toniigz_workflow('name', 1e-6)

.. autofunction:: TNT_pipeline_2.core_workflows.forceqform_workflow

   .. workflow::
      :graph2use: orig
      :simple_form: no

      from TNT_pipeline_2.core_workflows import forceqform_workflow
      wf = forceqform_workflow(['example_file'], 1e-6)
