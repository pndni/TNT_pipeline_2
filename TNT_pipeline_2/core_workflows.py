from collections import OrderedDict

from nipype.pipeline import engine as pe
from nipype import IdentityInterface, Merge
from pndniworkflows.interfaces import utils  # import GunzipOrIdent, MergeDictionaries, DictToString, Minc2AntsPoints, Ants2MincPoints
from pndniworkflows.interfaces import minc  # .minc import Nii2mnc, NUCorrect, Mnc2nii, INormalize, Classify
from nipype.interfaces import fsl
from nipype.interfaces.ants import resampling
from pndniworkflows.registration import ants_registration_syn_node
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
    outputspec = pe.Node(
        IdentityInterface(fields=['nu_bet', 'nu', 'normalized', 'brain_mask']),
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
            fields=['normalized', 'brain_mask', 'model', 'tags', 'model_brain_mask']),
        'inputspec')
    converttags = pe.Node(
        pndni_utils.ConvertPoints(out_format='ants'), 'converttags')

    nlreg = pe.Node(ants_registration_syn_node(verbose=True, num_threads=num_threads,
                                               smoothing_sigmas=[[3, 2, 1, 0], [3, 2, 1, 0], [2, 1, 0]],
                                               shrink_factors=[[8, 4, 2, 1], [8, 4, 2, 1], [4, 2, 1]],
                                               number_of_iterations=[[1000, 500, 250, 100],
                                                                     [1000, 500, 250, 100],
                                                                     [70, 50, 20]]), 'nlreg')
    merge_fixed = pe.Node(Merge(3), 'merge_fixed')
    merge_moving = pe.Node(Merge(3), 'merge_moving')
    merge_fixed.inputs.in3 = 'NULL'
    merge_moving.inputs.in3 = 'NULL'
    if debug:
        nlreg.inputs.number_of_iterations = [[1, 1, 1, 1], [1, 1, 1, 1],
                                             [1, 1, 1]]
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
            'transform',
            'inverse_transform',
            'warped_model',
            'transformed_model_brain_mask'
        ]),
        'outputspec')
    wf.connect([
        (inputspec, merge_fixed, [('brain_mask', 'in1'),
                                  ('brain_mask', 'in2')]),
        (inputspec, merge_moving, [('model_brain_mask', 'in1'),
                                   ('model_brain_mask', 'in2')]),
        (merge_fixed, nlreg, [('out', 'fixed_image_masks')]),
        (merge_moving, nlreg, [('out', 'moving_image_masks')]),
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
        (inputspec, extract_features, [('trminctags', 'tag_file'), ('brain_mask', 'mask_file')]),
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
            fields=['normalized', 'brain_mask', 'subcortical_model', 'subcortical_model_brain_mask', 'subcortical_atlas']),
        'inputspec')
    nlreg = pe.Node(ants_registration_syn_node(verbose=True, num_threads=num_threads), 'nlreg')
    if debug:
        nlreg.inputs.number_of_iterations = [[1, 1, 1, 1], [1, 1, 1, 1],
                                             [1, 1, 1, 1]]
    merge_fixed = pe.Node(Merge(3), 'merge_fixed')
    merge_moving = pe.Node(Merge(3), 'merge_moving')
    merge_fixed.inputs.in3 = 'NULL'
    merge_moving.inputs.in3 = 'NULL'

    tratlas = pe.Node(
        resampling.ApplyTransforms(dimension=3, interpolation='MultiLabel', num_threads=num_threads),
        'tratlas')
    outputspec = pe.Node(
        IdentityInterface(fields=[
            'subcortical_transform',
            'subcortical_inverse_transform',
            'warped_subcortical_model',
            'native_subcortical_atlas'
        ]),
        'outputspec')

    wf.connect([(inputspec,
                 nlreg,
                 [('normalized', 'fixed_image'),
                  ('subcortical_model', 'moving_image')]),
                (inputspec, merge_fixed, [('brain_mask', 'in1'),
                                          ('brain_mask', 'in2')]),
                (inputspec, merge_moving, [('subcortical_model_brain_mask', 'in1'),
                                           ('subcortical_model_brain_mask', 'in2')]),
                (merge_fixed, nlreg, [('out', 'fixed_image_masks')]),
                (merge_moving, nlreg, [('out', 'moving_image_masks')]),
                (inputspec, tratlas, [('subcortical_atlas', 'input_image')]),
                (nlreg, tratlas, [('composite_transform', 'transforms')]),
                (inputspec, tratlas, [('normalized', 'reference_image')]),
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
        IdentityInterface(fields=['icv_mask', 'transform', 'nu_bet']),
        'inputspec')
    tricv = pe.Node(
        resampling.ApplyTransforms(dimension=3,
                                   interpolation='NearestNeighbor',
                                   num_threads=num_threads),
        'tricv')
    outputspec = pe.Node(IdentityInterface(fields=['native_icv_mask']),
                         'outputspec')
    wf.connect([(inputspec,
                 tricv,
                 [('icv_mask', 'input_image'), ('transform', 'transforms'),
                  ('nu_bet', 'reference_image')]),
                (tricv, outputspec, [('output_image', 'native_icv_mask')])])
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
    inputfields = ['T1', 'model', 'tags', 'atlas', 'model_brain_mask']
    outputfields = [
        'T1',
        'model',
        'atlas',
        'model_brain_mask',
        'nu',
        'normalized',
        'brain_mask',
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
        inputfields.extend(['subcortical_model', 'subcortical_atlas', 'subcortical_model_brain_mask'])
        outputfields.extend([
            'subcortical_model',
            'subcortical_model_brain_mask',
            'subcortical_atlas',
            'subcortical_transform',
            'subcortical_inverse_transform',
            'warped_subcortical_model',
            'native_subcortical_atlas',
            'subcortical_stats'
        ])
    if icv:
        inputfields.extend(['icv_mask'])
        outputfields.extend(['icv_mask', 'native_icv_mask', 'icv_stats'])
    inputspec = pe.Node(IdentityInterface(fields=inputfields), 'inputspec')
    outputspec = pe.Node(IdentityInterface(fields=outputfields),
                         name='outputspec')
    qformfiles = inputfields.copy()
    qformfiles.pop(qformfiles.index('tags'))
    forceqform = forceqform_workflow(qformfiles, max_shear_angle)
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
    for qformf in qformfiles:
        wf.connect(inputspec, qformf, forceqform, f'inputspec.{qformf}')
        wf.connect(forceqform, f'outputspec.{qformf}', outputspec, qformf)

    wf.connect([
        (forceqform, pp, [('outputspec.T1', 'inputspec.T1')]),
        (forceqform,
         ants,
         [('outputspec.model', 'inputspec.model'),
          ('outputspec.model_brain_mask', 'inputspec.model_brain_mask')]),
        (inputspec, ants, [('tags', 'inputspec.tags')]),
        (pp, ants, [('outputspec.normalized', 'inputspec.normalized'),
                    ('outputspec.brain_mask', 'inputspec.brain_mask')]),
        (pp, classify, [('outputspec.nu_bet', 'inputspec.nu_bet'),
                        ('outputspec.brain_mask', 'inputspec.brain_mask')]),
        (ants, classify, [('outputspec.trminctags', 'inputspec.trminctags')]),
        (ants, segment, [('outputspec.transform', 'inputspec.transform')]),
        (classify,
         segment, [('outputspec.classified', 'inputspec.classified')]),
        (forceqform, segment, [('outputspec.atlas', 'inputspec.atlas')]),
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
         [('outputspec.transform', 'transform'),
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
            (forceqform,
             subcort,
             [('outputspec.subcortical_model', 'inputspec.subcortical_model'),
              ('outputspec.subcortical_atlas', 'inputspec.subcortical_atlas'),
              ('outputspec.subcortical_model_brain_mask', 'inputspec.subcortical_model_brain_mask')]),
            (pp, subcort, [('outputspec.normalized', 'inputspec.normalized'),
                           ('outputspec.brain_mask', 'inputspec.brain_mask')]),
            (subcort,
             outputspec,
             [('outputspec.subcortical_transform', 'subcortical_transform'),
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
            (forceqform, icv_wf, [('outputspec.icv_mask', 'inputspec.icv_mask')]),
            (pp, icv_wf, [('outputspec.nu_bet', 'inputspec.nu_bet')]),
            (ants, icv_wf, [('outputspec.transform', 'inputspec.transform')]),
            (icv_wf,
             outputspec, [('outputspec.native_icv_mask', 'native_icv_mask')]),
            (icv_wf,
             icv_stats, [
                 ('outputspec.native_icv_mask', 'inputspec.index_mask_file')
             ]), (pp, icv_stats, [('outputspec.nu', 'inputspec.in_file')]),
            (icv_stats, outputspec, [('outputspec.out_file', 'icv_stats')])
        ])
    return wf
