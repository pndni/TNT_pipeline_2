import argparse
from nipype.pipeline import engine as pe
from nipype import Rename
from pndniworkflows import utils
from pathlib import Path
import io
from bids import BIDSLayout

from .core_workflows import main_workflow
from .group import group_workflow
from . import output


PIPELINE_NAME = 'Toronto Pipeline'


def _get_scans(bidslayout, bids_filter, subject_list=None):
    t1wfilter = {'suffix': 'T1w',
                 'datatype': 'anat',
                 'extension': ['nii', 'nii.gz']}
    for key in bids_filter.keys():
        assert key not in t1wfilter.keys()
    if subject_list is None:
        subject_list = bidslayout.get_subjects()
    entities = []
    filenames = []
    for bidsfile in bidslayout.get(subject=subject_list, **t1wfilter, **bids_filter):
        tmp = bidsfile.get_entities()
        assert tmp.pop('datatype') == t1wfilter['datatype']
        assert tmp.pop('suffix') == t1wfilter['suffix']
        assert tmp.pop('extension') in t1wfilter['extension']
        entities.append(tmp)
        filenames.append(bidsfile.path)
    if not utils.unique(entities):
        raise RuntimeError('duplicate entities found')
    if not utils.unique(filenames):
        raise RuntimeError('duplicate filenames found')
    return list(zip(filenames, entities))


def t1_workflow(T1_scan, entities,
                atlas_labels_str,
                tissue_labels_str,
                tissue_and_atlas_labels, tissue_and_atlas_labels_str,
                outbidslayout, args):
    wf = pe.Workflow(name='T1_' + '_'.join((f'{key}-{val}' for key, val in entities.items())))
    io_out_wf = output.io_out_workflow(outbidslayout,
                                       entities,
                                       args.output_folder,
                                       args.model_space,
                                       atlas_labels_str,
                                       tissue_labels_str,
                                       tissue_and_atlas_labels_str)

    if args.debug_io:
        renametr = pe.Node(Rename(format_string='%(base)s.h5', parse_string='(?P<base>.*).nii(.gz)?'), 'renametr')
        renameitr = pe.Node(Rename(format_string='%(base)s.h5', parse_string='(?P<base>.*).nii(.gz)?'), 'renameitr')
        renamefeatures = pe.Node(Rename(format_string='%(base)s.txt', parse_string='(?P<base>.*).nii(.gz)?'), 'renamefeatures')
        renametr.inputs.in_file = T1_scan
        renameitr.inputs.in_file = T1_scan
        renamefeatures.inputs.in_file = T1_scan
        io_out_wf.inputs.inputspec.nu_bet = T1_scan
        io_out_wf.inputs.inputspec.normalized = T1_scan
        io_out_wf.inputs.inputspec.brain_mask = T1_scan
        io_out_wf.inputs.inputspec.warped_model = T1_scan
        io_out_wf.inputs.inputspec.classified = T1_scan
        io_out_wf.inputs.inputspec.transformed_atlas = T1_scan
        io_out_wf.inputs.inputspec.segmented = T1_scan
        io_out_wf.inputs.inputspec.stats = T1_scan
        io_out_wf.inputs.inputspec.brainstats = T1_scan
        io_out_wf.inputs.inputspec.transformed_model_brain_mask = T1_scan
        wf.connect([(renametr, io_out_wf, [('out_file', 'inputspec.transform')]),
                    (renameitr, io_out_wf, [('out_file', 'inputspec.inverse_transform')]),
                    (renamefeatures, io_out_wf, [('out_file', 'inputspec.features')])])
    else:
        main_wf = main_workflow(tissue_and_atlas_labels, debug=args.debug)
        main_wf.inputs.inputspec.bet_frac = args.bet_frac
        main_wf.inputs.inputspec.model = args.model
        main_wf.inputs.inputspec.tags = args.tags
        main_wf.inputs.inputspec.atlas = args.atlas
        main_wf.inputs.inputspec.model_brain_mask = args.model_brain_mask
        main_wf.inputs.inputspec.bet_vertical_gradient = args.bet_vertical_gradient
        main_wf.inputs.inputspec.T1 = T1_scan
        connectspec = [(f'outputspec.{connectname}', f'inputspec.{connectname}') for connectname in output.get_outputinfo(args.model_space).keys()]
        wf.connect([(main_wf, io_out_wf, connectspec)])

    crashdump_dir = outbidslayout.build_path({'rootdir': 'logs', **entities}, strict=True)
    if crashdump_dir is None:
        raise RuntimeError('unable to construct crashdump_dir')
    crashdump_dir = str(Path(outbidslayout.root, crashdump_dir))
    # Based on FMRIPREP https://github.com/poldracklab/fmriprep/blob/e8e740411d7c83c4af4526f82e862ae9363ab055/fmriprep/workflows/base.py#L265
    # apparently only configuration from the parent workflow is copied to nodes.
    for node in wf._get_all_nodes():
        if node.config is not None:
            raise RuntimeError('Expected node.config to be None')
        node.config = {'execution': {'crashdump_dir': crashdump_dir}}
    return wf


def _labels_to_str(labels):
    s = io.StringIO(newline='')
    utils.write_labels(s, labels)
    s.seek(0)
    return s.read()


def wrapper_workflow(args):
    inbidslayout = BIDSLayout(args.input_dataset, validate=not args.skip_validation)
    outbidslayout = utils.get_BIDSLayout_with_conf(args.output_folder, validate=False)
    atlas_labels = utils.read_labels(args.atlas_labels)
    atlas_labels_str = _labels_to_str(atlas_labels)
    tissue_labels = utils.read_labels(args.tag_labels)
    tissue_labels_str = _labels_to_str(tissue_labels)
    tissue_and_atlas_labels = utils.combine_labels(tissue_labels, atlas_labels)
    tissue_and_atlas_labels_str = _labels_to_str(tissue_and_atlas_labels)

    wf = pe.Workflow(name='wrapper')
    for T1_scan, T1_entities in _get_scans(inbidslayout, args.bids_filter,
                                           subject_list=args.participant_labels):
        tmpwf = t1_workflow(T1_scan, T1_entities,
                            atlas_labels_str,
                            tissue_labels_str,
                            tissue_and_atlas_labels,
                            tissue_and_atlas_labels_str,
                            outbidslayout,
                            args)
        wf.add_nodes([tmpwf])
    return wf


def _get_plugin_args(args):
    plugin_args = {}
    if args.n_proc is not None:
        if args.nipype_plugin != 'MultiProc':
            raise ValueError('--n_proc may only be specified with --nipype_plugin=MultiProc')
        plugin_args['n_proc'] = args.n_proc
    if args.nipype_plugin == 'Debug':
        def donothing(*args):
            pass
        plugin_args['callable'] = donothing
    return plugin_args


def run_participant(args):
    if args.atlas_labels is None:
        args.atlas_labels = _get_label_file(args.atlas, '--atlas_labels')
    if args.tag_labels is None:
        args.tag_labels = _get_label_file(args.tags, '--tag_labels')
    bids_filter = {}
    for filter_par in ['filter_session', 'filter_acquisition', 'filter_reconstruction', 'filter_run']:
        if filter_par in args:
            bids_filter[filter_par.split('_')[1]] = getattr(args, filter_par)
    args.bids_filter = bids_filter
    wf = wrapper_workflow(args)
    if args.working_directory is not None:
        if not args.working_directory.exists():
            raise FileNotFoundError('Specified working directory does not exist')
        wf.base_dir = str(args.working_directory)
    if args.graph_output is not None:
        wf.write_graph(graph2use='hierarchical', dotfilename=args.graph_output, format='dot')
        return
    wf.run(plugin=args.nipype_plugin, plugin_args=args.plugin_args)


def run_group(args):
    wf = group_workflow(args.output_folder, validate=not args.skip_validation)
    if args.working_directory is not None:
        if not args.working_directory.exists():
            raise FileNotFoundError('Specified working directory does not exist')
        wf.base_dir = str(args.working_directory)
    wf.run(plugin=args.nipype_plugin, plugin_args=args.plugin_args)


def _get_label_file(basefile, argstr):
    suffixes = ''.join(basefile.suffixes)
    labelfile = Path(basefile.parent, basefile.name[:-len(suffixes)] + '_labels.tsv')
    if not labelfile.exists():
        raise ValueError(f'No label file for {basefile} specified and {labelfile} does not exist. Use {argstr} to specify a label file')
    return labelfile


def _resolve_path(p):
    return Path(p).resolve()


# TODO BIDS style point file?
def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('input_dataset', type=_resolve_path, help='Location of `BIDS <https://bids-specification.readthedocs.io/en/stable/>`_ dataset')
    parser.add_argument('output_folder', type=_resolve_path, help='Output directory')
    parser.add_argument('analysis_level', type=str, choices=['participant', 'group'],
                        help='"participant" runs the main pipeline on each subject independently. "group" consolidates the results.')
    parser_b = parser.add_argument_group('General Arguments', description='Arguments for both group and participant analysis levels')
    parser_b.add_argument('--working_directory', type=_resolve_path, help='(Passed to the nipype workflow)')
    parser_b.add_argument('--skip_validation', action='store_true', help='Skip bids validation')
    # parser_g = parser.add_argument_group('group', description='Arguments for group analysis level')
    parser_p = parser.add_argument_group('Participant Arguments', description='Arguments for participant analysis level')
    parser_p.add_argument('--participant_labels', nargs='+', metavar='PARTICIPANT_LABEL',
                          help='Subjects on which to run the pipeline. If not specified, run on all.')
    parser_p.add_argument('--model', type=_resolve_path, default='/template/SYS_808.nii',
                          help='A model/template brain in the same space as "--atlas" and "--tags". '
                               'Will be registered with T1w images to map template space to native space.')
    parser_p.add_argument('--model_space', type=str, default='SYS808',
                          help='The name of the model space. Used only for naming files.')
    parser_p.add_argument('--atlas', type=_resolve_path, default='/template/SYS808_atlas_labels_nomiddle.nii',
                          help='Atlas in model/template space subdividing the brain into lobes. '
                               'This atlas will be transformed to native space and combined with the GM and WM maps.')
    parser_p.add_argument('--atlas_labels', type=_resolve_path,
                          help='A BIDS style label file (i.e. a tab-separated values file with "index" and "name" columns '
                               'described in `BEP011 <https://docs.google.com/document/d/1YG2g4UkEio4t_STIBOqYOwneLEs1emHIXbGKynx7V0Y/edit#heading=h.g35a71g5bvrk>`_). '
                               'Describes the lobes in "atlas". If not specified will look for a file with the same '
                               'name ias "--atlas" but ending in "_labels.tsv".')
    parser_p.add_argument('--tags', type=_resolve_path, default='/template/ntags_1000_prob_90_nobg_sys808.tag',
                          help='`An MNI point file <https://en.wikibooks.org/wiki/MINC/SoftwareDevelopment/Tag_file_format_reference>`_ '
                               'labeling GM, WM, and CSF.')
    parser_p.add_argument('--tag_labels', type=_resolve_path, help='A label file mapping the labels in "--tags" to tissue names.')
    parser_p.add_argument('--model_brain_mask', type=_resolve_path, default='/template/SYS808_brainmask.nii',
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
    filter_parameters = ['filter_session', 'filter_acquisition', 'filter_reconstruction', 'filter_run']
    for filter_par in filter_parameters:
        filter_par_short = filter_par.split('_')[1]
        helpstr = f'Use only T1w scans that have {filter_par_short} parameter {filter_par_short.upper()}. '
        helpstr += 'If this parameter is set without an argument, only scans '
        helpstr += f'which do not have the {filter_par_short} parameter will be selected.'
        parser_p.add_argument(f'--{filter_par}', type=str, help=helpstr, metavar=filter_par_short.upper(),
                              nargs='?', const=None, default=argparse.SUPPRESS)
    parser_p.add_argument('--nipype_plugin', type=str, choices=['Linear', 'MultiProc', 'Debug'],
                          help='Specify the nipype workflow execution plugin. "Linear" will aid debugging.')
    parser_p.add_argument('--n_proc', type=int,
                          help='The number of processors to use with the MultiProc plugin. If not set determine automatically.')
    return parser


def main():
    parser = get_parser()
    args = parser.parse_args()
    args.plugin_args = _get_plugin_args(args)
    if args.analysis_level == 'participant':
        run_participant(args)
    elif args.analysis_level == 'group':
        run_group(args)
    else:
        raise ValueError('Invalid value for analysis_level. How did you get here?')


if __name__ == '__main__':
    main()
