from collections import OrderedDict

from nipype.pipeline import engine as pe
from nipype import IdentityInterface, Merge
from pndniworkflows.interfaces import utils  # import GunzipOrIdent, MergeDictionaries, DictToString, Minc2AntsPoints, Ants2MincPoints
from pndniworkflows.interfaces import minc  # .minc import Nii2mnc, NUCorrect, Mnc2nii, INormalize, Classify
from nipype.interfaces import fsl
from nipype.interfaces.ants import resampling
from pndniworkflows.registration import ants_registration_syn_no_affine_node, ants_registration_affine_node
from pndniworkflows.interfaces import pndni_utils
from pndniworkflows.postprocessing import image_stats_wf


def forceqform_workflow(files, max_shear_angle):
    wf = pe.Workflow(name='forceqform')
    inputspec = pe.Node(IdentityInterface(fields=files), 'inputspec')
    outputspec = pe.Node(IdentityInterface(fields=files), 'outputspec')
    for f in files:
        node = pe.Node(pndni_utils.ForceQForm(out_file=f'{f}_qform.nii.gz', maxangle=max_shear_angle), f'forceqc_{f}')
        wf.connect(inputspec, f, node, 'in_file')
        wf.connect(node, 'out_file', outputspec, f)
    return wf


def tomnc_workflow(wfname):
    wf = pe.Workflow(name=wfname)
    inputspec = pe.Node(IdentityInterface(fields=['in_file']), 'inputspec')
    gunzip = pe.Node(utils.GunzipOrIdent(), 'gunzip')
    convert = pe.Node(minc.Nii2mnc(), 'convert')
    outputspec = pe.Node(IdentityInterface(fields=['out_file']), 'outputspec')
    wf.connect(inputspec, 'in_file', gunzip, 'in_file')
    wf.connect(gunzip, 'out_file', convert, 'in_file')
    wf.connect(convert, 'out_file', outputspec, 'out_file')
    return wf


def toniigz_workflow(wfname, max_shear_angle, **kwargs):
    wf = pe.Workflow(name=wfname)
    inputspec = pe.Node(IdentityInterface(fields=['in_file']), 'inputspec')
    fix_dircos = pe.Node(
        pndni_utils.MncDefaultDircos(),
        'fix_dircos')
    convert = pe.Node(minc.Mnc2nii(**kwargs), 'convert')
    forceqform = pe.Node(pndni_utils.ForceQForm(maxangle=max_shear_angle), 'forceqform')
    gzip = pe.Node(utils.Gzip(), 'gzip')
    outputspec = pe.Node(IdentityInterface(fields=['out_file']), 'outputspec')
    wf.connect(inputspec, 'in_file', fix_dircos, 'in_file')
    wf.connect(fix_dircos, 'out_file', convert, 'in_file')
    wf.connect(convert, 'out_file', forceqform, 'in_file')
    wf.connect(forceqform, 'out_file', gzip, 'in_file')
    wf.connect(gzip, 'out_file', outputspec, 'out_file')
    return wf


def preproc_workflow(bet_frac,
                     bet_vertical_gradient,
                     inormalize_const2,
                     inormalize_range,
                     max_shear_angle):
    wf = pe.Workflow(name="preproc")
    inputspec = pe.Node(IdentityInterface(fields=['T1']), 'inputspec')
    tomnc_wf = tomnc_workflow('to_mnc')
    nu_correct = pe.Node(minc.NUCorrect(), 'nu_correct')
    nuc_mnc_to_nii = toniigz_workflow('nuc_mnc_to_nii', max_shear_angle)
    inorm = pe.Node(
        minc.INormalize(const2=inormalize_const2, range=inormalize_range),
        'inorm')
    inorm_mnc_to_nii = toniigz_workflow('inorm_mnc_to_nii', max_shear_angle)
    bet = pe.Node(
        fsl.BET(mask=True,
                frac=bet_frac,
                vertical_gradient=bet_vertical_gradient),
        'bet')
    mask = pe.Node(fsl.ImageMaths(), 'mask')
    masknormalized = pe.Node(fsl.ImageMaths(), 'masknormalized')
    outputspec = pe.Node(
        IdentityInterface(fields=['nu_bet', 'nu', 'normalized', 'brain_mask', 'normalized_brain']),
        'outputspec')
    wf.connect(inputspec, 'T1', tomnc_wf, 'inputspec.in_file')
    wf.connect(tomnc_wf, 'outputspec.out_file', nu_correct, 'in_file')
    wf.connect(nu_correct, 'out_file', inorm, 'in_file')
    wf.connect(inorm, 'out_file', inorm_mnc_to_nii, 'inputspec.in_file')
    wf.connect(inorm_mnc_to_nii, 'outputspec.out_file', bet, 'in_file')
    wf.connect(nu_correct, 'out_file', nuc_mnc_to_nii, 'inputspec.in_file')
    wf.connect(nuc_mnc_to_nii, 'outputspec.out_file', mask, 'in_file')
    wf.connect(bet, 'mask_file', mask, 'mask_file')
    wf.connect(mask, 'out_file', outputspec, 'nu_bet')
    wf.connect(inorm_mnc_to_nii, 'outputspec.out_file', masknormalized, 'in_file')
    wf.connect(bet, 'mask_file', masknormalized, 'mask_file')
    wf.connect(masknormalized, 'out_file', outputspec, 'normalized_brain')
    wf.connect(bet, 'mask_file', outputspec, 'brain_mask')
    wf.connect(inorm_mnc_to_nii,
               'outputspec.out_file',
               outputspec,
               'normalized')
    wf.connect(nuc_mnc_to_nii, 'outputspec.out_file', outputspec, 'nu')
    return wf


def ants_workflow(debug=False, num_threads=1):
    wf = pe.Workflow(name='ants')
    inputspec = pe.Node(
        IdentityInterface(
            fields=['normalized', 'normalized_brain', 'model', 'tags', 'model_brain', 'model_brain_mask']),
        'inputspec')
    converttags = pe.Node(
        pndni_utils.ConvertPoints(out_format='ants'), 'converttags')
    linreg = pe.Node(ants_registration_affine_node(verbose=True, num_threads=num_threads), 'linreg')
    nlreg = pe.Node(ants_registration_syn_no_affine_node(verbose=True, num_threads=num_threads), 'nlreg')
    if debug:
        linreg.inputs.number_of_iterations = [[1, 1, 1, 1], [1, 1, 1, 1]]
        nlreg.inputs.number_of_iterations = [[1, 1, 1, 1]]
    trinvmerge = pe.Node(Merge(1), 'trinvmerge')
    trpoints = pe.Node(resampling.ApplyTransformsToPoints(dimension=3, num_threads=num_threads),
                       'trpoints')
    converttags2 = pe.Node(
        pndni_utils.ConvertPoints(out_format='minc'),
        'converttags2')
    trbrain = pe.Node(
        resampling.ApplyTransforms(dimension=3,
                                   interpolation='NearestNeighbor',
                                   num_threads=num_threads),
        'trbrain')
    outputspec = pe.Node(
        IdentityInterface(fields=[
            'trminctags',
            'linear_transform',
            'transform',
            'inverse_transform',
            'warped_model',
            'transformed_model_brain_mask'
        ]),
        'outputspec')
    wf.connect([
        (inputspec, linreg, [('normalized_brain', 'fixed_image'),
                             ('model_brain', 'moving_image')]),
        (linreg, nlreg, [('composite_transform', 'initial_moving_transform')]),
        (inputspec,
         nlreg, [('normalized', 'fixed_image'), ('model', 'moving_image')]),
        (nlreg, trinvmerge, [('inverse_composite_transform', 'in1')]),
        (trinvmerge, trpoints, [('out', 'transforms')]),
        (inputspec, converttags, [('tags', 'in_file')]),
        (converttags, trpoints, [('out_file', 'input_file')]),
        (trpoints, converttags2, [('output_file', 'in_file')]),
        (converttags2, outputspec, [('out_file', 'trminctags')]),
        (inputspec,
         trbrain,
         [('model_brain_mask', 'input_image'),
          ('normalized', 'reference_image')]),
        (nlreg, trbrain, [('composite_transform', 'transforms')]),
        (linreg, outputspec, [('composite_transform', 'linear_transform')]),
        (nlreg,
         outputspec,
         [('composite_transform', 'transform'),
          ('inverse_composite_transform', 'inverse_transform'),
          ('warped_image', 'warped_model')]),
        (trbrain,
         outputspec, [('output_image', 'transformed_model_brain_mask')]),
    ])
    return wf


def classify_workflow(max_shear_angle):
    wf = pe.Workflow(name='classify')
    inputspec = pe.Node(
        IdentityInterface(fields=['nu_bet', 'trminctags', 'brain_mask']),
        'inputspec')
    tomnc = tomnc_workflow('to_mnc')
    tomnc_brain_mask = tomnc_workflow('to_mnc_brain_mask')
    classify = pe.Node(minc.Classify(), 'classify')
    extract_features = pe.Node(minc.Classify(dump_features=True),
                               'extract_features')
    convert_features = pe.Node(utils.Csv2Tsv(header=['value', 'index']),
                               'convert_features')
    tonii = toniigz_workflow(
        'mnc2nii', max_shear_angle, write_byte=True,
        write_unsigned=True)  # TODO can I always assume this?
    outputspec = pe.Node(IdentityInterface(fields=['classified', 'features']),
                         'outputspec')
    # TODO points outside mask?
    wf.connect([
        (inputspec, tomnc_brain_mask, [('brain_mask', 'inputspec.in_file')]),
        (inputspec,
         classify, [('trminctags', 'tag_file')]),
        (tomnc_brain_mask, classify, [('outputspec.out_file', 'mask_file')]),
        (inputspec, tomnc, [('nu_bet', 'inputspec.in_file')]),
        (tomnc, classify, [('outputspec.out_file', 'in_file')]),
        (classify, tonii, [('out_file', 'inputspec.in_file')]),
        (tonii, outputspec, [('outputspec.out_file', 'classified')]),
        (inputspec, extract_features, [('trminctags', 'tag_file')]),
        (tomnc_brain_mask, extract_features, [('outputspec.out_file', 'mask_file')]),
        (tomnc, extract_features, [('outputspec.out_file', 'in_file')]),
        (extract_features, convert_features, [('features', 'in_file')]),
        (convert_features, outputspec, [('out_file', 'features')]),
    ])
    return wf


def segment_lobes_workflow(num_threads=1):
    wf = pe.Workflow(name='segment_lobes')
    inputspec = pe.Node(
        IdentityInterface(fields=['classified', 'transform', 'atlas']),
        'inputspec')
    tratlas = pe.Node(
        resampling.ApplyTransforms(dimension=3, interpolation='MultiLabel', num_threads=num_threads),
        'tratlas')
    labelsmerge = pe.Node(Merge(2), name='labelsmerge')
    combinelabels = pe.Node(pndni_utils.CombineLabels(), name='combinelabels')
    outputspec = pe.Node(
        IdentityInterface(fields=['segmented', 'transformed_atlas']),
        name='outputspec')
    wf.connect([
        (inputspec,
         tratlas,
         [('transform', 'transforms'), ('atlas', 'input_image'),
          ('classified', 'reference_image')]),
        (inputspec, labelsmerge, [('classified', 'in1')]),
        (tratlas, labelsmerge, [('output_image', 'in2')]),
        (labelsmerge, combinelabels, [('out', 'label_files')]),
        (combinelabels, outputspec, [('out_file', 'segmented')]),
        (tratlas, outputspec, [('output_image', 'transformed_atlas')]),
    ])
    return wf


def subcortical_workflow(debug=False, num_threads=1):
    wf = pe.Workflow(name='subcortical')
    inputspec = pe.Node(
        IdentityInterface(
            fields=['normalized', 'normalized_brain', 'subcortical_model', 'subcortical_model_brain', 'subcortical_atlas']),
        'inputspec')
    linreg = pe.Node(ants_registration_affine_node(verbose=True, num_threads=num_threads), 'linreg')
    nlreg = pe.Node(ants_registration_syn_no_affine_node(verbose=True, num_threads=num_threads), 'nlreg')
    if debug:
        linreg.inputs.number_of_iterations = [[1, 1, 1, 1], [1, 1, 1, 1]]
        nlreg.inputs.number_of_iterations = [[1, 1, 1, 1]]

    tratlas = pe.Node(
        resampling.ApplyTransforms(dimension=3, interpolation='MultiLabel', num_threads=num_threads),
        'tratlas')
    outputspec = pe.Node(
        IdentityInterface(fields=[
            'subcortical_linear_transform',
            'subcortical_transform',
            'subcortical_inverse_transform',
            'warped_subcortical_model',
            'native_subcortical_atlas'
        ]),
        'outputspec')

    wf.connect([(inputspec, linreg, [('normalized_brain', 'fixed_image'),
                                     ('subcortical_model_brain', 'moving_image')]),
                (inputspec,
                 nlreg,
                 [('normalized', 'fixed_image'),
                  ('subcortical_model', 'moving_image')]),
                (linreg, nlreg, [('composite_transform', 'initial_moving_transform')]),
                (inputspec, tratlas, [('subcortical_atlas', 'input_image'),
                                      ('normalized', 'reference_image')]),
                (nlreg, tratlas, [('composite_transform', 'transforms')]),
                (linreg, outputspec, [('composite_transform', 'subcortical_linear_transform')]),
                (nlreg,
                 outputspec,
                 [('composite_transform', 'subcortical_transform'),
                  ('inverse_composite_transform',
                   'subcortical_inverse_transform'),
                  ('warped_image', 'warped_subcortical_model')]),
                (tratlas,
                 outputspec, [('output_image', 'native_subcortical_atlas')])])
    return wf


def icv_workflow(num_threads=1):
    wf = pe.Workflow('icv')
    inputspec = pe.Node(
        IdentityInterface(fields=['intracranial_mask', 'transform', 'nu_bet']),
        'inputspec')
    tricv = pe.Node(
        resampling.ApplyTransforms(dimension=3,
                                   interpolation='NearestNeighbor',
                                   num_threads=num_threads),
        'tricv')
    outputspec = pe.Node(IdentityInterface(fields=['native_intracranial_mask']),
                         'outputspec')
    wf.connect([(inputspec,
                 tricv,
                 [('intracranial_mask', 'input_image'), ('transform', 'transforms'),
                  ('nu_bet', 'reference_image')]),
                (tricv, outputspec, [('output_image', 'native_intracranial_mask')])])
    return wf


def main_workflow(statslabels,
                  bet_frac,
                  bet_vertical_gradient,
                  inormalize_const2,
                  inormalize_range,
                  subcortical=False,
                  subcort_statslabels=None,
                  icv=False,
                  debug=False,
                  max_shear_angle=1e-6,
                  num_threads=1):
    wf = pe.Workflow(name='main')
    inputfields = ['T1', 'model', 'tags', 'atlas', 'model_brain_mask', 'model_brain']
    outputfields = [
        'T1',
        'nu',
        'normalized',
        'brain_mask',
        'linear_transform',
        'transform',
        'inverse_transform',
        'warped_model',
        'classified',
        'features',
        'segmented',
        'transformed_atlas',
        'stats',
        'brainstats',
        'transformed_model_brain_mask'
    ]
    if subcortical:
        inputfields.extend(['subcortical_model', 'subcortical_atlas', 'subcortical_model_brain_mask', 'subcortical_model_brain'])
        outputfields.extend([
            'subcortical_linear_transform',
            'subcortical_transform',
            'subcortical_inverse_transform',
            'warped_subcortical_model',
            'native_subcortical_atlas',
            'subcortical_stats'
        ])
    if icv:
        inputfields.extend(['intracranial_mask'])
        outputfields.extend(['native_intracranial_mask', 'icv_stats'])
    inputspec = pe.Node(IdentityInterface(fields=inputfields), 'inputspec')
    outputspec = pe.Node(IdentityInterface(fields=outputfields),
                         name='outputspec')
    forceqform = pe.Node(pndni_utils.ForceQForm(out_file='T1_qform.nii.gz', maxangle=max_shear_angle), 'forceqc_T1')
    pp = preproc_workflow(bet_frac,
                          bet_vertical_gradient,
                          inormalize_const2,
                          inormalize_range,
                          max_shear_angle)
    ants = ants_workflow(debug=debug, num_threads=num_threads)
    classify = classify_workflow(max_shear_angle)
    segment = segment_lobes_workflow(num_threads=num_threads)
    stats = image_stats_wf(['volume', 'mean'], statslabels, 'stats')
    brainstats = image_stats_wf(['volume', 'mean'],
                                [OrderedDict(index=1, name='brain')],
                                'brainstats')
    wf.connect(inputspec, 'T1', forceqform, 'in_file')
    wf.connect(forceqform, 'out_file', outputspec, 'T1')

    wf.connect([
        (forceqform, pp, [('out_file', 'inputspec.T1')]),
        (inputspec,
         ants,
         [('model', 'inputspec.model'),
          ('model_brain', 'inputspec.model_brain'),
          ('model_brain_mask', 'inputspec.model_brain_mask'),
          ('tags', 'inputspec.tags')]),
        (pp, ants, [('outputspec.normalized', 'inputspec.normalized'),
                    ('outputspec.normalized_brain', 'inputspec.normalized_brain')]),
        (pp, classify, [('outputspec.nu_bet', 'inputspec.nu_bet'),
                        ('outputspec.brain_mask', 'inputspec.brain_mask')]),
        (ants, classify, [('outputspec.trminctags', 'inputspec.trminctags')]),
        (ants, segment, [('outputspec.transform', 'inputspec.transform')]),
        (classify,
         segment, [('outputspec.classified', 'inputspec.classified')]),
        (inputspec, segment, [('atlas', 'inputspec.atlas')]),
        (segment,
         stats, [('outputspec.segmented', 'inputspec.index_mask_file')]),
        (pp, stats, [('outputspec.nu', 'inputspec.in_file')]),
        (ants,
         brainstats,
         [('outputspec.transformed_model_brain_mask',
           'inputspec.index_mask_file')]),
        (pp, brainstats, [('outputspec.nu', 'inputspec.in_file')]),
        (pp,
         outputspec,
         [('outputspec.nu', 'nu'),
          ('outputspec.normalized', 'normalized'),
          ('outputspec.brain_mask', 'brain_mask')]),
        (ants,
         outputspec,
         [('outputspec.linear_transform', 'linear_transform'),
          ('outputspec.transform', 'transform'),
          ('outputspec.inverse_transform', 'inverse_transform'),
          ('outputspec.warped_model', 'warped_model'),
          ('outputspec.transformed_model_brain_mask',
           'transformed_model_brain_mask')]),
        (classify,
         outputspec,
         [('outputspec.classified', 'classified'),
          ('outputspec.features', 'features')]),
        (segment,
         outputspec,
         [('outputspec.segmented', 'segmented'),
          ('outputspec.transformed_atlas', 'transformed_atlas')]),
        (stats, outputspec, [('outputspec.out_file', 'stats')]),
        (brainstats, outputspec, [('outputspec.out_file', 'brainstats')]),
    ])
    if subcortical:
        if subcort_statslabels is None:
            raise ValueError(
                'subcort_statslabels must not be None if subcortical is True')
        subcort = subcortical_workflow(debug=debug, num_threads=num_threads)
        subcort_stats = image_stats_wf(['volume', 'mean'],
                                       subcort_statslabels,
                                       'subcortical_stats')
        wf.connect([
            (inputspec,
             subcort,
             [('subcortical_model', 'inputspec.subcortical_model'),
              ('subcortical_atlas', 'inputspec.subcortical_atlas'),
              ('subcortical_model_brain', 'inputspec.subcortical_model_brain')]),
            (pp, subcort, [('outputspec.normalized', 'inputspec.normalized'),
                           ('outputspec.normalized_brain', 'inputspec.normalized_brain')]),
            (subcort,
             outputspec,
             [('outputspec.subcortical_linear_transform', 'subcortical_linear_transform'),
              ('outputspec.subcortical_transform', 'subcortical_transform'),
              ('outputspec.subcortical_inverse_transform',
               'subcortical_inverse_transform'),
              ('outputspec.warped_subcortical_model',
               'warped_subcortical_model'),
              ('outputspec.native_subcortical_atlas',
               'native_subcortical_atlas')]),
            (pp, subcort_stats, [('outputspec.nu', 'inputspec.in_file')]),
            (subcort,
             subcort_stats,
             [('outputspec.native_subcortical_atlas',
               'inputspec.index_mask_file')]),
            (subcort_stats,
             outputspec, [('outputspec.out_file', 'subcortical_stats')])
        ])
    if icv:
        icv_wf = icv_workflow(num_threads=num_threads)
        icv_stats = image_stats_wf(['volume'],
                                   [OrderedDict(index=1, name='ICV')],
                                   'icv_stats')
        wf.connect([
            (inputspec, icv_wf, [('intracranial_mask', 'inputspec.intracranial_mask')]),
            (pp, icv_wf, [('outputspec.nu_bet', 'inputspec.nu_bet')]),
            (ants, icv_wf, [('outputspec.transform', 'inputspec.transform')]),
            (icv_wf,
             outputspec, [('outputspec.native_intracranial_mask', 'native_intracranial_mask')]),
            (icv_wf,
             icv_stats, [
                 ('outputspec.native_intracranial_mask', 'inputspec.index_mask_file')
             ]),
            (pp, icv_stats, [('outputspec.nu', 'inputspec.in_file')]),
            (icv_stats, outputspec, [('outputspec.out_file', 'icv_stats')])
        ])
    return wf
