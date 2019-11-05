from nipype.pipeline import engine as pe
from nipype import Rename
from pndniworkflows import utils
from pathlib import Path
from bids import BIDSLayout

from .core_workflows import main_workflow
from . import output
from .utils import _update_workdir, read_json, adjust_node_name
from nipype.interfaces import fsl
from . import logger


def participant_workflow(args):
    fsl.FSLCommand.set_default_output_type('NIFTI_GZ')
    inbidslayout = BIDSLayout(args.input_dataset,
                              validate=not args.skip_validation)
    outbidslayout = utils.get_BIDSLayout_with_conf(args.output_folder,
                                                   validate=False)

    wf = pe.Workflow(name='participant')
    for T1_scan, T1_entities in _get_scans(
            inbidslayout, args.bids_filter,
            subject_list=args.participant_labels):
        tmpwf = t1_workflow(T1_scan, T1_entities, outbidslayout, args)
        wf.add_nodes([tmpwf])
    _update_workdir(wf, args.working_directory)
    if args.resource_input_file is not None:
        _set_resource_data(wf, args.resource_input_file)
    return wf


def _get_all_nodes(wf, name=None):
    """ based on nipypes Workflow._get_all_nodes, but keeps
    track of full node name"""
    if name is None:
        name = []
    else:
        name = name.copy()
    name.append(wf.name)
    for node in wf._graph.nodes():
        if isinstance(node, pe.Workflow):
            yield from _get_all_nodes(node, name)
        else:
            yield ('.'.join(name + [node.name]), node)


def _set_resource_data(wf, fname):
    data = read_json(fname)
    for fullname, node in _get_all_nodes(wf):
        nameadj = adjust_node_name(fullname)
        if nameadj in data:
            if not hasattr(node._interface.inputs, 'num_threads'):
                node.n_procs = int(data[nameadj]['ncpu'])
            # This is a bit of a hack because Node does not define a setter
            # for mem_gb
            node._mem_gb = float(data[nameadj]['mem'])
            logger.info(f'Set {node} (fullname {fullname}) _mem_gb to {node._mem_gb} and n_procs to {node.n_procs}')


def t1_workflow(T1_scan, entities, outbidslayout, args):
    wf = pe.Workflow(name='T1_' +
                     '_'.join((f'{key}-{val}'
                               for key, val in entities.items())))
    io_out_wf = output.io_out_workflow(
        outbidslayout,
        entities,
        args.output_folder,
        args.model_space,
        args.atlas_labels.string,
        args.tissue_labels.string,
        args.tissue_and_atlas_labels.string,
        subcortical=args.subcortical,
        subcortical_model_space=args.subcortical_model_space,
        subcortical_labels_str=args.subcortical_labels.string,
        intracranial_volume=args.intracranial_volume,
        debug=args.debug_io)

    if args.debug_io:
        renametr = pe.Node(
            Rename(format_string='%(base)s.h5',
                   parse_string='(?P<base>.*).nii(.gz)?'),
            'renametr')
        renameitr = pe.Node(
            Rename(format_string='%(base)s.h5',
                   parse_string='(?P<base>.*).nii(.gz)?'),
            'renameitr')
        renamefeatures = pe.Node(
            Rename(format_string='%(base)s.tsv',
                   parse_string='(?P<base>.*).nii(.gz)?'),
            'renamefeatures')
        renametr.inputs.in_file = T1_scan
        renameitr.inputs.in_file = T1_scan
        renamefeatures.inputs.in_file = T1_scan
        io_out_wf.inputs.inputspec.T1 = T1_scan
        io_out_wf.inputs.inputspec.model = T1_scan
        io_out_wf.inputs.inputspec.atlas = T1_scan
        io_out_wf.inputs.inputspec.model_brain_mask = T1_scan
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
        wf.connect([(renametr,
                     io_out_wf, [('out_file', 'inputspec.transform')]),
                    (renameitr,
                     io_out_wf, [('out_file', 'inputspec.inverse_transform')]),
                    (renamefeatures,
                     io_out_wf, [('out_file', 'inputspec.features')])])
        if args.subcortical:
            renamesubtr = pe.Node(
                Rename(format_string='%(base)s.h5',
                       parse_string='(?P<base>.*).nii(.gz)?'),
                'renamesubtr')
            renamesubitr = pe.Node(
                Rename(format_string='%(base)s.h5',
                       parse_string='(?P<base>.*).nii(.gz)?'),
                'renamesubitr')
            renamesubtr.inputs.in_file = T1_scan
            renamesubitr.inputs.in_file = T1_scan
            io_out_wf.inputs.inputspec.subcortical_model = T1_scan
            io_out_wf.inputs.inputspec.subcortical_atlas = T1_scan
            io_out_wf.inputs.inputspec.warped_subcortical_model = T1_scan
            io_out_wf.inputs.inputspec.native_subcortical_atlas = T1_scan
            io_out_wf.inputs.inputspec.subcortical_stats = T1_scan
            wf.connect([
                (renamesubtr,
                 io_out_wf, [('out_file', 'inputspec.subcortical_transform')]),
                (renamesubitr,
                 io_out_wf, [('out_file',
                              'inputspec.subcortical_inverse_transform')])
            ])
        if args.intracranial_volume:
            io_out_wf.inputs.inputspec.icv_mask = T1_scan
            io_out_wf.inputs.inputspec.native_icv_mask = T1_scan
            io_out_wf.inputs.inputspec.icv_stats = T1_scan
    else:
        main_wf = main_workflow(
            args.tissue_and_atlas_labels.labels,
            args.bet_frac,
            args.bet_vertical_gradient,
            args.inormalize_const2,
            args.inormalize_range,
            debug=args.debug,
            subcortical=args.subcortical,
            subcort_statslabels=args.subcortical_labels.labels,
            icv=args.intracranial_volume,
            max_shear_angle=args.max_shear_angle)
        main_wf.inputs.inputspec.model = args.model
        main_wf.inputs.inputspec.tags = args.tags
        main_wf.inputs.inputspec.atlas = args.atlas
        main_wf.inputs.inputspec.model_brain_mask = args.model_brain_mask
        main_wf.inputs.inputspec.T1 = T1_scan
        if args.subcortical:
            main_wf.inputs.inputspec.subcortical_model = args.subcortical_model
            main_wf.inputs.inputspec.subcortical_atlas = args.subcortical_atlas
        if args.intracranial_volume:
            main_wf.inputs.inputspec.icv_mask = args.intracranial_mask
        connectspec = [(f'outputspec.{connectname}',
                        f'inputspec.{connectname}')
                       for connectname in output.get_outputinfo(
                           args.model_space,
                           args.subcortical,
                           args.subcortical_model_space,
                           args.intracranial_volume).keys()]
        wf.connect([(main_wf, io_out_wf, connectspec)])

    crashdump_dir = outbidslayout.build_path({
        'rootdir': 'logs', **entities
    },
                                             strict=True,
                                             validate=False)
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


def _get_scans(bidslayout, bids_filter, subject_list=None):
    t1wfilter = {
        'suffix': 'T1w', 'datatype': 'anat', 'extension': ['nii', 'nii.gz']
    }
    for key in bids_filter.keys():
        assert key not in t1wfilter.keys()
    if subject_list is None:
        subject_list = bidslayout.get_subjects()
    entities = []
    filenames = []
    for bidsfile in bidslayout.get(subject=subject_list,
                                   **t1wfilter,
                                   **bids_filter):
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
