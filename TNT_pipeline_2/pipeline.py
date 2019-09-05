import argparse
from nipype.pipeline import engine as pe
from nipype.interfaces.fsl import BET, ImageMaths
from nipype.interfaces.ants.resampling import ApplyTransforms, ApplyTransformsToPoints
from nipype import IdentityInterface, Merge, Function
from nipype.interfaces.utility import Rename
from pndniworkflows.interfaces.pndni_utils import CombineLabels
from pndniworkflows.interfaces.minc import Nii2mnc, NUCorrect, Mnc2nii, INormalize, Classify
from pndniworkflows.interfaces.utils import GunzipOrIdent, MergeDictionaries, DictToString, Minc2AntsPoints, Ants2MincPoints
from pndniworkflows.interfaces.io import WriteBIDSFile, CombineStats
from pndniworkflows.interfaces.reports import (ReportletCompare,
                                               AssembleReport,
                                               ReportletContour,
                                               ReportletDistributions,
                                               IndexReport)
from pndniworkflows import utils
from pndniworkflows.registration import ants_registration_syn_node
from pndniworkflows.postprocessing import image_stats_wf
from pathlib import Path
from bids import BIDSLayout
from collections import OrderedDict
import sys


PIPELINE_NAME = 'Toronto Pipeline'


def tomnc_workflow():
    wf = pe.Workflow(name="to_mnc")
    inputspec = pe.Node(IdentityInterface(fields=['in_file']), 'inputspec')
    gunzip = pe.Node(GunzipOrIdent(), 'gunzip')
    convert = pe.Node(Nii2mnc(), 'convert')
    outputspec = pe.Node(IdentityInterface(fields=['out_file']), 'outputspec')
    wf.connect(inputspec, 'in_file', gunzip, 'in_file')
    wf.connect(gunzip, 'out_file', convert, 'in_file')
    wf.connect(convert, 'out_file', outputspec, 'out_file')
    return wf


def preproc_workflow():
    wf = pe.Workflow(name="preproc")
    inputspec = pe.Node(IdentityInterface(fields=['T1', 'bet_frac', 'bet_vertical_gradient']), 'inputspec')
    tomnc_wf = tomnc_workflow()
    nu_correct = pe.Node(NUCorrect(), 'nu_correct')
    nuc_mnc_to_nii = pe.Node(Mnc2nii(), 'nuc_mnc_to_nii')
    inorm = pe.Node(INormalize(const2=[0.0, 5000.0], range=1.0), 'inorm')
    inorm_mnc_to_nii = pe.Node(Mnc2nii(), 'inorm_mnc_to_nii')
    bet = pe.Node(BET(mask=True), 'bet')
    mask = pe.Node(ImageMaths(), 'mask')
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


def ants_workflow(debug=False):
    wf = pe.Workflow(name='ants')
    inputspec = pe.Node(IdentityInterface(fields=['normalized', 'model', 'tags', 'brain_mask', 'model_brain_mask']), 'inputspec')
    converttags = pe.Node(Minc2AntsPoints(flipxy=True), 'converttags')
    nlreg = pe.Node(ants_registration_syn_node(),
                    'nlreg')
    nlreg.inputs.verbose = True
    if debug:
        nlreg.inputs.number_of_iterations = [[1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1]]
    trinvmerge = pe.Node(Merge(1), 'trinmerge')
    trpoints = pe.Node(ApplyTransformsToPoints(dimension=3), 'trpoints')
    converttags2 = pe.Node(Ants2MincPoints(flipxy=True), 'converttags2')
    trbrain = pe.Node(ApplyTransforms(dimension=3, interpolation='NearestNeighbor'), 'trbrain')
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
    classify = pe.Node(Classify(), 'classify')
    extract_features = pe.Node(Classify(dump_features=True), 'extract_features')
    tonii = pe.Node(Mnc2nii(write_byte=True, write_unsigned=True), 'mnc2nii')  # TODO can I always assume this?
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
    tratlas = pe.Node(ApplyTransforms(dimension=3, interpolation='MultiLabel'), 'tratlas')
    labelsmerge = pe.Node(Merge(2), name='labelsmerge')
    combinelabels = pe.Node(CombineLabels(), name='combinelabels')
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


def main_workflow(statslabels, debug=False):
    wf = pe.Workflow(name='main')
    inputspec = pe.Node(IdentityInterface(fields=['T1',
                                                  'bet_frac',
                                                  'bet_vertical_gradient',
                                                  'model',
                                                  'tags',
                                                  'atlas',
                                                  'model_brain_mask']),
                        'inputspec')
    pp = preproc_workflow()
    ants = ants_workflow(debug=debug)
    classify = classify_workflow()
    segment = segment_lobes_workflow()
    stats = image_stats_wf(['volume', 'mean'], statslabels, 'stats')
    brainstats = image_stats_wf(['volume', 'mean'], [OrderedDict(index=1, name='brain')], 'brainstats')
    outputspec = pe.Node(IdentityInterface(fields=['nu_bet',
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
                                                   'transformed_model_brain_mask']),
                         name='outputspec')
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
    return wf


def _get_scans_node(bids_dir, bids_filter, validate, subject_list=None):
    t1wfilter = {'suffix': 'T1w',
                 'datatype': 'anat',
                 'extension': ['nii', 'nii.gz']}
    for key in bids_filter.keys():
        assert key not in t1wfilter.keys()
    scans = pe.Node(IdentityInterface(fields=['entities']), name='scans')
    bids = BIDSLayout(bids_dir, validate=validate)
    if subject_list is None:
        subject_list = bids.get_subjects()
    entities = []
    for bidsfile in bids.get(subject=subject_list, **t1wfilter, **bids_filter):
        tmp = bidsfile.get_entities()
        assert tmp.pop('datatype') == t1wfilter['datatype']
        assert tmp.pop('suffix') == t1wfilter['suffix']
        assert tmp.pop('extension') in t1wfilter['extension']
        entities.append(tmp)
    if not utils.unique(entities):
        raise RuntimeError('duplicate entities found')
    scans.iterables = [('entities', entities)]
    return scans


def _gett1(bids_dir, entities, validate):
    from bids import BIDSLayout
    t1wfilter = {'suffix': 'T1w',
                 'datatype': 'anat',
                 'extension': ['nii', 'nii.gz']}
    for key in entities.keys():
        assert key not in t1wfilter.keys()
    searchparams = {**t1wfilter, **entities}
    searchparams.setdefault('acquisition', None)
    searchparams.setdefault('reconstruction', None)
    searchparams.setdefault('run', None)
    bids = BIDSLayout(bids_dir, validate)
    bidsfiles = bids.get(**searchparams)
    if len(bidsfiles) != 1:
        raise RuntimeError(f'{len(bidsfiles)} files found for entities ' + ', '.join(f'{key}: {val}' for key, val in entities.items()))
    return bidsfiles[0].path


def io_in_workflow(input_dataset, participant_labels, bids_filter, validate):
    wf = pe.Workflow(name='io_in')
    # get node which iterates on unique image properties
    scans = _get_scans_node(input_dataset, bids_filter, validate, subject_list=participant_labels)
    # gett1 file from each set of properties. The reason this is split into two nodes is to prevent
    # nipype from making a subfolder with the path in the directory name, which would happen if
    # we iterated on path. This would cause bet (and maybe other FSL tools) to choke, as the extension
    # in the path would get stripped out
    gett1 = pe.Node(Function(input_names=['bids_dir', 'entities', 'validate'], output_names=['T1'], function=_gett1), 'gett1')
    gett1.inputs.bids_dir = input_dataset
    gett1.inputs.validate = validate
    # if multiple files found, run the pipeline on each
    outputspec = pe.Node(IdentityInterface(fields=['T1', 'entities']), 'outputspec')
    wf.connect([(scans, outputspec, [('entities', 'entities')]),
                (scans, gett1, [('entities', 'entities')]),
                (gett1, outputspec, [('T1', 'T1')]),
                ])
    return wf


def io_out_workflow(output_folder, model_space, atlas_labels, tissue_labels, tissue_and_atlas_labels, qc=True):

    wf = pe.Workflow(name='io_out')
    outputfiles = {}
    outputfiles['nu_bet'] = ({'skullstripped': 'true',
                              'description': 'nucor',
                              'suffix': 'T1w'},
                             None)
    outputfiles['normalized'] = ({'skullstripped': 'true',
                                  'description': 'normalized',
                                  'suffix': 'T1w'},
                                 None)
    outputfiles['brain_mask'] = ({'description': 'brain',
                                  'suffix': 'mask',
                                  'space': 'T1w'},
                                 None)
    outputfiles['transform'] = ({'from_': model_space,
                                 'to': 'T1w',
                                 'suffix': 'xfm',
                                 'mode': 'image'},
                                None)
    outputfiles['inverse_transform'] = ({'to': model_space,
                                         'from_': 'T1w',
                                         'suffix': 'xfm',
                                         'mode': 'image'},
                                        None)
    outputfiles['warped_model'] = ({'space': 'T1w',
                                    'suffix': 'T1w',
                                    'map_': model_space},
                                   None)
    outputfiles['transformed_model_brain_mask'] = ({'space': 'T1w',
                                                    'suffix': 'mask',
                                                    'map_': model_space,
                                                    'description': 'brain'},
                                                   None)
    outputfiles['classified'] = ({'suffix': 'dseg',
                                  'space': 'T1w',
                                  'description': 'tissue'},
                                 tissue_labels)
    outputfiles['transformed_atlas'] = ({'suffix': 'dseg',
                                         'space': 'T1w',
                                         'description': 'lobes'},
                                        atlas_labels)
    outputfiles['segmented'] = ({'suffix': 'dseg',
                                 'space': 'T1w',
                                 'description': 'tissue+lobes'},
                                tissue_and_atlas_labels)
    outputfiles['stats'] = ({'suffix': 'stats', 'description': 'tissue+lobes'}, None)
    outputfiles['brainstats'] = ({'suffix': 'stats', 'description': 'brain'}, None)
    inputspec = pe.Node(IdentityInterface(fields=list(outputfiles.keys()) + ['T1', 'features', 'entities']), 'inputspec')
    for sourcename, (bidsinfo, labelinfo) in outputfiles.items():
        propnode = pe.Node(MergeDictionaries(in1=bidsinfo), 'propnode' + sourcename)
        node = pe.Node(WriteBIDSFile(), name='write' + sourcename)
        if labelinfo is not None:
            node.inputs.labelinfo = labelinfo
        node.inputs.out_dir = output_folder
        wf.connect([(inputspec, propnode, [('entities', 'in2')]),
                    (propnode, node, [('out', 'bidsparams')]),
                    (inputspec, node, [(sourcename, 'in_file')])])

    # TODO output QC
    if qc:
        tissue_map = {row['index']: row['name'] for row in tissue_labels}
        reportlets = pe.Node(Merge(6), 'reportlets')
        _connect_compare(wf, reportlets, 1, 'T1', (inputspec, 'T1'), 'NU Correct', (inputspec, 'nu_bet'))
        _connect_compare(wf, reportlets, 2, 'T1', (inputspec, 'T1'), 'Normalized', (inputspec, 'normalized'))
        _connect_compare(wf, reportlets, 3, 'T1', (inputspec, 'T1'), 'Warped Model', (inputspec, 'warped_model'))
        _connect_dists(wf, reportlets, 4, 'Labeled Tissue Distribution', (inputspec, 'features'), tissue_map)
        _connect_contour(wf, reportlets, 5, 'Tissue Classification', (inputspec, 'T1'), (inputspec, 'classified'))
        _connect_contour(wf, reportlets, 6, 'Lobar Classification', (inputspec, 'T1'), (inputspec, 'transformed_atlas'))
        get_title = pe.Node(DictToString(keys={'subject': 'sub',
                                               'acquisition': 'acq',
                                               'reconstruction': 'rec',
                                               'run': 'run'}),
                            'get_title')
        assemble_node = pe.Node(AssembleReport(), 'assemble')
        writeqc = pe.Node(WriteBIDSFile(), name='writeqc')
        writeqc.inputs.out_dir = output_folder
        wf.connect([(inputspec, writeqc, [('entities', 'bidsparams')]),
                    (inputspec, get_title, [('entities', 'dictionary')]),
                    (get_title, assemble_node, [('out', 'title')]),
                    (reportlets, assemble_node, [('out', 'in_files')]),
                    (assemble_node, writeqc, [('out_file', 'in_file')])])
    return wf


def wrapper_workflow(input_dataset, output_folder, participant_labels, model, model_space, atlas, atlas_labels_file,
                     tags, tag_labels_file, model_brain_mask, bet_frac, bet_vertical_gradient, bids_filter, debug=False, debug_io=False,
                     validate=True):
    qc = True
    if debug_io:
        qc = False
    atlas_labels = utils.read_labels(atlas_labels_file)
    tissue_labels = utils.read_labels(tag_labels_file)
    tissue_and_atlas_labels = utils.combine_labels(tissue_labels, atlas_labels)
    wf = pe.Workflow(name='wrapper')
    io_in_wf = io_in_workflow(input_dataset, participant_labels, bids_filter, validate)
    io_out_wf = io_out_workflow(output_folder, model_space, atlas_labels, tissue_labels, tissue_and_atlas_labels, qc=qc)
    if debug_io:
        renametr = pe.Node(Rename(format_string='%(base)s.h5', parse_string='(?P<base>.*).nii(.gz)?'), 'renametr')
        renameitr = pe.Node(Rename(format_string='%(base)s.h5', parse_string='(?P<base>.*).nii(.gz)?'), 'renameitr')
        wf.connect([(io_in_wf, io_out_wf, [('outputspec.T1', 'inputspec.T1'),
                                           ('outputspec.T1', 'inputspec.nu_bet'),
                                           ('outputspec.entities', 'inputspec.entities'),
                                           ('outputspec.T1', 'inputspec.normalized'),
                                           ('outputspec.T1', 'inputspec.brain_mask'),
                                           ('outputspec.T1', 'inputspec.warped_model'),
                                           ('outputspec.T1', 'inputspec.classified'),
                                           ('outputspec.T1', 'inputspec.transformed_atlas'),
                                           ('outputspec.T1', 'inputspec.segmented'),
                                           ('outputspec.T1', 'inputspec.stats'),
                                           ('outputspec.T1', 'inputspec.brainstats'),
                                           ('outputspec.T1', 'inputspec.transformed_model_brain_mask')]),
                    (io_in_wf, renametr, [('outputspec.T1', 'in_file')]),
                    (renametr, io_out_wf, [('out_file', 'inputspec.transform')]),
                    (io_in_wf, renameitr, [('outputspec.T1', 'in_file')]),
                    (renameitr, io_out_wf, [('out_file', 'inputspec.inverse_transform')])])
    else:

        main_wf = main_workflow(tissue_and_atlas_labels, debug=debug)
        main_wf.inputs.inputspec.bet_frac = bet_frac
        main_wf.inputs.inputspec.model = model
        main_wf.inputs.inputspec.tags = tags
        main_wf.inputs.inputspec.atlas = atlas
        main_wf.inputs.inputspec.model_brain_mask = model_brain_mask
        main_wf.inputs.inputspec.bet_vertical_gradient = bet_vertical_gradient
        wf.connect([(io_in_wf, main_wf, [('outputspec.T1', 'inputspec.T1')]),
                    (main_wf, io_out_wf, [('outputspec.nu_bet', 'inputspec.nu_bet'),
                                          ('outputspec.normalized', 'inputspec.normalized'),
                                          ('outputspec.brain_mask', 'inputspec.brain_mask'),
                                          ('outputspec.transform', 'inputspec.transform'),
                                          ('outputspec.inverse_transform', 'inputspec.inverse_transform'),
                                          ('outputspec.warped_model', 'inputspec.warped_model'),
                                          ('outputspec.classified', 'inputspec.classified'),
                                          ('outputspec.features', 'inputspec.features'),
                                          ('outputspec.transformed_atlas', 'inputspec.transformed_atlas'),
                                          ('outputspec.segmented', 'inputspec.segmented'),
                                          ('outputspec.stats', 'inputspec.stats'),
                                          ('outputspec.brainstats', 'inputspec.brainstats'),
                                          ('outputspec.transformed_model_brain_mask', 'inputspec.transformed_model_brain_mask')]),
                    (io_in_wf, io_out_wf, [('outputspec.entities', 'inputspec.entities'),
                                           ('outputspec.T1', 'inputspec.T1')])])

    return wf


def _connect_compare(wf, reportlets, num, name1, desc1, name2, desc2):
    compare_node = pe.Node(ReportletCompare(), f'compare{num}')
    compare_node.inputs.name1 = name1
    compare_node.inputs.name2 = name2
    wf.connect(desc1[0], desc1[1], compare_node, 'image1')
    wf.connect(desc2[0], desc2[1], compare_node, 'image2')
    wf.connect(compare_node, 'out_file', reportlets, f'in{num}')


def _connect_contour(wf, reportlets, num, name, desc, labeldesc):
    contour_node = pe.Node(ReportletContour(), f'contour{num}')
    contour_node.inputs.name = name
    wf.connect(desc[0], desc[1], contour_node, 'image')
    wf.connect(labeldesc[0], labeldesc[1], contour_node, 'labelimage')
    wf.connect(contour_node, 'out_file', reportlets, f'in{num}')


def _connect_dists(wf, reportlets, num, name, desc, labelmap):
    dists_node = pe.Node(ReportletDistributions(), f'dists{num}')
    dists_node.inputs.name = name
    wf.connect(desc[0], desc[1], dists_node, 'distsfile')
    dists_node.inputs.labelmap = labelmap
    wf.connect(dists_node, 'out_file', reportlets, f'in{num}')


def group_workflow(out_dir, validate):
    groupdir = out_dir / 'group'
    groupdir.mkdir(exist_ok=True)
    outfile = groupdir / 'group.tsv'
    # if outfile.exists():
    #     raise FileExistsError(f'{outfile} exists')
    wf = pe.Workflow('group')
    combine = pe.Node(CombineStats(bids_dir=str(out_dir),
                                   validate=validate,
                                   row_keys=['subject', 'acquisition', 'reconstruction', 'rec'],
                                   invariants={'datatype': 'anat', 'extension': 'tsv'},
                                   index='name',
                                   ignore={'index'}),
                       'combine')
    write = pe.Node(Rename(format_string=str(outfile)), 'write')
    wf.connect(combine, 'out_tsv', write, 'in_file')

    html_files = [str(html_f.resolve()) for html_f in out_dir.glob('sub*/**/*html')]
    index_file = str((groupdir / 'group.html').resolve())
    indexreport = pe.Node(IndexReport(out_file=index_file, in_files=html_files), 'indexreport')
    wf.add_nodes([indexreport])

    return wf


def _get_label_file(basefile, argstr):
    suffixes = ''.join(basefile.suffixes)
    labelfile = Path(basefile.parent, basefile.name[:-len(suffixes)] + '_labels.tsv')
    if not labelfile.exists():
        raise ValueError(f'No label file for {basefile} specified and {labelfile} does not exist. Use {argstr} to specify a label file')
    return labelfile


# TODO BIDS style point file?
def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('input_dataset', type=Path, help='Location of `BIDS <https://bids-specification.readthedocs.io/en/stable/>`_ dataset')
    parser.add_argument('output_folder', type=Path, help='Output directory')
    parser.add_argument('analysis_level', type=str, choices=['participant', 'group'],
                        help='"participant" runs the main pipeline on each subject independently. "group" consolidates the results.')
    parser_b = parser.add_argument_group('General Arguments', description='Arguments for both group and participant analysis levels')
    parser_b.add_argument('--working_directory', type=Path, help='(Passed to the nipype workflow)')
    parser_b.add_argument('--skip_validation', action='store_true', help='Skip bids validation')
    # parser_g = parser.add_argument_group('group', description='Arguments for group analysis level')
    parser_p = parser.add_argument_group('Participant Arguments', description='Arguments for participant analysis level')
    parser_p.add_argument('--participant_labels', nargs='+', metavar='PARTICIPANT_LABEL',
                          help='Subjects on which to run the pipeline. If not specified, run on all.')
    parser_p.add_argument('--model', type=Path, default='/template/SYS_808.nii',
                          help='A model/template brain in the same space as "--atlas" and "--tags". '
                               'Will be registered with T1w images to map template space to native space.')
    parser_p.add_argument('--model_space', type=str, default='SYS808',
                          help='The name of the model space. Used only for naming files.')
    parser_p.add_argument('--atlas', type=Path, default='/template/SYS808_atlas_labels_nomiddle.nii',
                          help='Atlas in model/template space subdividing the brain into lobes. '
                               'This atlas will be transformed to native space and combined with the GM and WM maps.')
    parser_p.add_argument('--atlas_labels', type=Path,
                          help='A BIDS style label file (i.e. a tab-separated values file with "index" and "name" columns '
                               'described in `BEP011 <https://docs.google.com/document/d/1YG2g4UkEio4t_STIBOqYOwneLEs1emHIXbGKynx7V0Y/edit#heading=h.g35a71g5bvrk>`_). '
                               'Describes the lobes in "atlas". If not specified will look for a file with the same '
                               'name ias "--atlas" but ending in "_labels.tsv".')
    parser_p.add_argument('--tags', type=Path, default='/template/ntags_1000_prob_90_nobg_sys808.tag',
                          help='`An MNI point file <https://en.wikibooks.org/wiki/MINC/SoftwareDevelopment/Tag_file_format_reference>`_ '
                               'labeling GM, WM, and CSF.')
    parser_p.add_argument('--tag_labels', type=Path, help='A label file mapping the labels in "--tags" to tissue names.')
    parser_p.add_argument('--model_brain_mask', type=Path, default='/template/SYS808_brainmask.nii',
                          help='Brain mask in model/template space.')
    parser_p.add_argument('--bet_frac', type=float, default=0.5,
                          help='Argument passed to FSL\'s BET')
    parser_p.add_argument('--bet_vertical_gradient', type=float, default=0.0,
                          help='Argument passed to FSL\'s BET')
    parser_p.add_argument('--debug', action='store_true',
                          help='Set ANTs iteration count to 1 to make the workflow fast.')
    parser_p.add_argument('--debug_io', action='store_true',
                          help='Bypass main workflow to test the input/output logic.')
    parser_p.add_argument('--graph_output', type=str,
                          help='Generate a graph of the workflow and save as "--graph_output".')
    filter_parameters = ['filter_acquisition', 'filter_reconstruction', 'filter_run']
    for filter_par in filter_parameters:
        filter_par_short = filter_par.split('_')[1]
        helpstr = f'Use only T1w scans that have {filter_par_short} parameter {filter_par_short.upper()}. '
        helpstr += 'If this parameter is set without an argument, only scans '
        helpstr += f'which do not have the {filter_par_short} parameter will be selected.'
        parser_p.add_argument(f'--{filter_par}', type=str, help=helpstr, metavar=filter_par_short.upper(),
                              nargs='?', const=None, default=argparse.SUPPRESS)
    parser_p.add_argument('--nipype_plugin', type=str, choices=['Linear', 'MultiProc'],
                          help='Specify the nipype workflow execution plugin. "Linear" will aid debugging.')
    parser_p.add_argument('--n_proc', type=int,
                          help='The number of processors to use with the MultiProc plugin. If not set determine automatically.')
    return parser


def main():
    parser = get_parser()
    args = parser.parse_args()
    if args.analysis_level == 'participant':
        if args.atlas_labels is None:
            args.atlas_labels = _get_label_file(args.atlas, '--atlas_labels')
        if args.tag_labels is None:
            args.tag_labels = _get_label_file(args.tags, '--tag_labels')
        bids_filter = {}
        for filter_par in ['filter_acquisition', 'filter_reconstruction', 'filter_run']:
            if filter_par in args:
                bids_filter[filter_par.split('_')[1]] = getattr(args, filter_par)
        wf = wrapper_workflow(str(args.input_dataset.resolve()),
                              str(args.output_folder.resolve()),
                              args.participant_labels,
                              str(args.model.resolve()),
                              args.model_space,
                              str(args.atlas.resolve()),
                              str(args.atlas_labels.resolve()),
                              str(args.tags.resolve()),
                              str(args.tag_labels.resolve()),
                              str(args.model_brain_mask.resolve()),
                              args.bet_frac,
                              args.bet_vertical_gradient,
                              bids_filter,
                              debug=args.debug,
                              debug_io=args.debug_io,
                              validate=not args.skip_validation)
        if args.graph_output is not None:
            wf.write_graph(graph2use='hierarchical', dotfilename=args.graph_output, format='dot')
        else:
            if args.working_directory is not None:
                if not args.working_directory.exists():
                    raise FileNotFoundError('Specified working directory does not exist')
                wf.base_dir = str(args.working_directory.resolve())
            plugin_args = {}
            if args.n_proc is not None:
                if args.nipype_plugin != 'MultiProc':
                    raise ValueError('--n_proc may only be specified with --nipype_plugin=MultiProc')
                plugin_args['n_proc'] = args.n_proc
            wf.run(plugin=args.nipype_plugin, plugin_args=plugin_args)
    elif args.analysis_level == 'group':
        wf = group_workflow(args.output_folder.resolve(), not args.skip_validation)
        if args.working_directory is not None:
            if not args.working_directory.exists():
                raise FileNotFoundError('Specified working directory does not exist')
            wf.base_dir = str(args.working_directory.resolve())
        wf.run()
    else:
        raise ValueError('Invalid value for analysis_level. How did you get here?')


if __name__ == '__main__':
    main()
