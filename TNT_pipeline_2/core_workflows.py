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


def tomnc_workflow():
    wf = pe.Workflow(name="to_mnc")
    inputspec = pe.Node(IdentityInterface(fields=['in_file']), 'inputspec')
    gunzip = pe.Node(utils.GunzipOrIdent(), 'gunzip')
    convert = pe.Node(minc.Nii2mnc(), 'convert')
    outputspec = pe.Node(IdentityInterface(fields=['out_file']), 'outputspec')
    wf.connect(inputspec, 'in_file', gunzip, 'in_file')
    wf.connect(gunzip, 'out_file', convert, 'in_file')
    wf.connect(convert, 'out_file', outputspec, 'out_file')
    return wf


def preproc_workflow():
    wf = pe.Workflow(name="preproc")
    inputspec = pe.Node(IdentityInterface(fields=['T1', 'bet_frac', 'bet_vertical_gradient']), 'inputspec')
    tomnc_wf = tomnc_workflow()
    nu_correct = pe.Node(minc.NUCorrect(), 'nu_correct')
    nuc_mnc_to_nii = pe.Node(minc.Mnc2nii(), 'nuc_mnc_to_nii')
    inorm = pe.Node(minc.INormalize(const2=[0.0, 5000.0], range=1.0), 'inorm')
    inorm_mnc_to_nii = pe.Node(minc.Mnc2nii(), 'inorm_mnc_to_nii')
    bet = pe.Node(fsl.BET(mask=True), 'bet')
    mask = pe.Node(fsl.ImageMaths(), 'mask')
    outputspec = pe.Node(IdentityInterface(fields=['nu_bet', 'normalized', 'brain_mask']), 'outputspec')
    wf.connect(inputspec, 'T1', tomnc_wf, 'inputspec.in_file')
    wf.connect(tomnc_wf, 'outputspec.out_file', nu_correct, 'in_file')
    wf.connect(nu_correct, 'out_file', inorm, 'in_file')
    wf.connect(inorm, 'out_file', inorm_mnc_to_nii, 'in_file')
    wf.connect(inorm_mnc_to_nii, 'out_file', bet, 'in_file')
    wf.connect(inputspec, 'bet_frac', bet, 'frac')
    wf.connect(inputspec, 'bet_vertical_gradient', bet, 'vertical_gradient')
    wf.connect(nu_correct, 'out_file', nuc_mnc_to_nii, 'in_file')
    wf.connect(nuc_mnc_to_nii, 'out_file', mask, 'in_file')
    wf.connect(bet, 'mask_file', mask, 'mask_file')
    wf.connect(mask, 'out_file', outputspec, 'nu_bet')
    wf.connect(bet, 'mask_file', outputspec, 'brain_mask')
    wf.connect(inorm_mnc_to_nii, 'out_file', outputspec, 'normalized')
    return wf


def subcortitcal_workflow(debug=False):
    wf = pe.Workflow(name='subcortical')
    inputspec = pe.Node(IdentityInterface(fields=['normalized',
                                                  'subcortical_model',
                                                  'subcortical_atlas']),
                        'inputspec')
    nlreg = pe.Node(ants_registration_syn_node(verbose=True), 'nlreg')
    if debug:
        nlreg.inputs.number_of_iterations = [[1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1]]
    tratlas = pe.Node(resampling.ApplyTransforms(dimension=3, interpolation='MultiLabel'), 'tratlas')
    outputspec = pe.Node(IdentityInterface(fields=['subcortical_transform',
                                                   'subcortical_inverse_transform',
                                                   'warped_subcortical_model',
                                                   'native_subcortical_atlas']),
                         'outputspec')

    wf.connect([(inputspec, nlreg, [('normalized', 'fixed_image'),
                                    ('subcortical_model', 'moving_image')]),
                (inputspec, tratlas, [('subcortical_atlas', 'input_image')]),
                (nlreg, tratlas, [('composite_transform', 'transforms')]),
                (nlreg, outputspec, [('composite_transform', 'subcortical_transform'),
                                     ('inverse_composite_transform', 'subcortical_inverse_transform'),
                                     ('warped_image', 'warped_subcortical_model')]),
                (tratlas, outputspec, [('output_image', 'native_subcortical_atlas')])])
    return wf


def ants_workflow(debug=False):
    wf = pe.Workflow(name='ants')
    inputspec = pe.Node(IdentityInterface(fields=['normalized', 'model', 'tags', 'brain_mask', 'model_brain_mask']), 'inputspec')
    converttags = pe.Node(utils.Minc2AntsPoints(flipxy=True), 'converttags')
    nlreg = pe.Node(ants_registration_syn_node(verbose=True),
                    'nlreg')
    if debug:
        nlreg.inputs.number_of_iterations = [[1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1]]
    trinvmerge = pe.Node(Merge(1), 'trinmerge')
    trpoints = pe.Node(resampling.ApplyTransformsToPoints(dimension=3), 'trpoints')
    converttags2 = pe.Node(utils.Ants2MincPoints(flipxy=True), 'converttags2')
    trbrain = pe.Node(resampling.ApplyTransforms(dimension=3, interpolation='NearestNeighbor'), 'trbrain')
    outputspec = pe.Node(IdentityInterface(fields=['trtags', 'transform', 'inverse_transform', 'warped_model', 'transformed_model_brain_mask']), 'outputspec')
    wf.connect([(inputspec, nlreg, [('normalized', 'fixed_image'),
                                    ('model', 'moving_image'),
                                    ('brain_mask', 'fixed_image_masks')]),
                (nlreg, trinvmerge, [('inverse_composite_transform', 'in1')]),
                (trinvmerge, trpoints, [('out', 'transforms')]),
                (inputspec, converttags, [('tags', 'in_file')]),
                (converttags, trpoints, [('out_file', 'input_file')]),
                (trpoints, converttags2, [('output_file', 'in_file')]),
                (converttags2, outputspec, [('out_file', 'trtags')]),
                (inputspec, trbrain, [('model_brain_mask', 'input_image'),
                                      ('normalized', 'reference_image')]),
                (nlreg, trbrain, [('composite_transform', 'transforms')]),
                (nlreg, outputspec, [('composite_transform', 'transform'),
                                     ('inverse_composite_transform', 'inverse_transform'),
                                     ('warped_image', 'warped_model')]),
                (trbrain, outputspec, [('output_image', 'transformed_model_brain_mask')]),
                ])
    return wf


def classify_workflow():
    wf = pe.Workflow(name='classify')
    inputspec = pe.Node(IdentityInterface(fields=['nu_bet', 'trtags', 'brain_mask']), 'inputspec')
    tomnc = tomnc_workflow()
    classify = pe.Node(minc.Classify(), 'classify')
    extract_features = pe.Node(minc.Classify(dump_features=True), 'extract_features')
    tonii = pe.Node(minc.Mnc2nii(write_byte=True, write_unsigned=True), 'mnc2nii')  # TODO can I always assume this?
    outputspec = pe.Node(IdentityInterface(fields=['classified', 'features']), 'outputspec')
    # TODO points outside mask?
    wf.connect([(inputspec, classify, [('trtags', 'tag_file'),
                                       ('brain_mask', 'mask_file')]),
                (inputspec, tomnc, [('nu_bet', 'inputspec.in_file')]),
                (tomnc, classify, [('outputspec.out_file', 'in_file')]),
                (classify, tonii, [('out_file', 'in_file')]),
                (tonii, outputspec, [('out_file', 'classified')]),
                (inputspec, extract_features, [('trtags', 'tag_file')]),
                (tomnc, extract_features, [('outputspec.out_file', 'in_file')]),
                (extract_features, outputspec, [('features', 'features')]),
                ])
    return wf


def segment_lobes_workflow():
    wf = pe.Workflow(name='segment_lobes')
    inputspec = pe.Node(IdentityInterface(fields=['classified', 'transform', 'atlas']), 'inputspec')
    tratlas = pe.Node(resampling.ApplyTransforms(dimension=3, interpolation='MultiLabel'), 'tratlas')
    labelsmerge = pe.Node(Merge(2), name='labelsmerge')
    combinelabels = pe.Node(pndni_utils.CombineLabels(), name='combinelabels')
    outputspec = pe.Node(IdentityInterface(fields=['segmented', 'transformed_atlas']), name='outputspec')
    wf.connect([(inputspec, tratlas, [('transform', 'transforms'),
                                      ('atlas', 'input_image'),
                                      ('classified', 'reference_image')]),
                (inputspec, labelsmerge, [('classified', 'in1')]),
                (tratlas, labelsmerge, [('output_image', 'in2')]),
                (labelsmerge, combinelabels, [('out', 'label_files')]),
                (combinelabels, outputspec, [('out_file', 'segmented')]),
                (tratlas, outputspec, [('output_image', 'transformed_atlas')]),
                ])
    return wf


def main_workflow(statslabels, subcortical=True, subcort_statslabels=None, debug=False):
    wf = pe.Workflow(name='main')
    inputfields = ['T1',
                   'bet_frac',
                   'bet_vertical_gradient',
                   'model',
                   'tags',
                   'atlas',
                   'model_brain_mask']
    outputfields = ['nu_bet',
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
                    'transformed_model_brain_mask']
    if subcortical:
        inputfields.extend(['subcortical_model',
                            'subcortical_atlas'])
        outputfields.extend(['subcortical_transform',
                             'subcortical_inverse_transform',
                             'warped_subcortical_model',
                             'native_subcortical_atlas',
                             'subcortical_stats'])
    inputspec = pe.Node(IdentityInterface(fields=inputfields), 'inputspec')
    outputspec = pe.Node(IdentityInterface(fields=outputfields), name='outputspec')
    pp = preproc_workflow()
    ants = ants_workflow(debug=debug)
    classify = classify_workflow()
    segment = segment_lobes_workflow()
    stats = image_stats_wf(['volume', 'mean'], statslabels, 'stats')
    brainstats = image_stats_wf(['volume', 'mean'], [OrderedDict(index=1, name='brain')], 'brainstats')
    wf.connect([
        (inputspec, pp, [('T1', 'inputspec.T1'),
                         ('bet_frac', 'inputspec.bet_frac'),
                         ('bet_vertical_gradient', 'inputspec.bet_vertical_gradient')]),
        (inputspec, ants, [('model', 'inputspec.model'),
                           ('tags', 'inputspec.tags'),
                           ('model_brain_mask', 'inputspec.model_brain_mask')]),
        (pp, ants, [('outputspec.normalized', 'inputspec.normalized'),
                    ('outputspec.brain_mask', 'inputspec.brain_mask')]),
        (pp, classify, [('outputspec.nu_bet', 'inputspec.nu_bet')]),
        (ants, classify, [('outputspec.trtags', 'inputspec.trtags')]),
        (ants, segment, [('outputspec.transform', 'inputspec.transform')]),
        (classify, segment, [('outputspec.classified', 'inputspec.classified')]),
        (inputspec, segment, [('atlas', 'inputspec.atlas')]),
        (segment, stats, [('outputspec.segmented', 'inputspec.index_mask_file')]),
        (pp, stats, [('outputspec.nu_bet', 'inputspec.in_file')]),
        (ants, brainstats, [('outputspec.transformed_model_brain_mask', 'inputspec.index_mask_file')]),
        (pp, brainstats, [('outputspec.nu_bet', 'inputspec.in_file')]),
        (pp, outputspec, [('outputspec.nu_bet', 'nu_bet'),
                          ('outputspec.normalized', 'normalized'),
                          ('outputspec.brain_mask', 'brain_mask')]),
        (ants, outputspec, [('outputspec.transform', 'transform'),
                            ('outputspec.inverse_transform', 'inverse_transform'),
                            ('outputspec.warped_model', 'warped_model'),
                            ('outputspec.transformed_model_brain_mask', 'transformed_model_brain_mask')]),
        (classify, outputspec, [('outputspec.classified', 'classified'),
                                ('outputspec.features', 'features')]),
        (segment, outputspec, [('outputspec.segmented', 'segmented'),
                               ('outputspec.transformed_atlas', 'transformed_atlas')]),
        (stats, outputspec, [('outputspec.out_file', 'stats')]),
        (brainstats, outputspec, [('outputspec.out_file', 'brainstats')]),
        ])
    if subcortical:
        if subcort_statslabels is None:
            raise ValueError('subcort_statslabels must not be None if subcortical is True')
        subcort = subcortitcal_workflow(debug=debug)
        subcort_stats = image_stats_wf(['volume', 'mean'], subcort_statslabels, 'subcortical_stats')
        wf.connect([(inputspec, subcort, [('subcortical_model', 'inputspec.subcortical_model'),
                                          ('subcortical_atlas', 'inputspec.subcortical_atlas')]),
                    (pp, subcort, [('outputspec.normalized', 'inputspec.normalized')]),
                    (subcort, outputspec, [('outputspec.subcortical_transform', 'subcortical_transform'),
                                           ('outputspec.subcortical_inverse_transform', 'subcortical_inverse_transform'),
                                           ('outputspec.warped_subcortical_model', 'warped_subcortical_model'),
                                           ('outputspec.native_subcortical_atlas', 'native_subcortical_atlas')]),
                    (pp, subcort_stats, [('outputspec.nu_bet', 'inputspec.in_file')]),
                    (subcort, subcort_stats, [('outputspec.native_subcortical_atlas', 'inputspec.index_mask_file')]),
                    (subcort_stats, outputspec, [('outputspec.out_file', 'subcortical_stats')])])
    return wf
