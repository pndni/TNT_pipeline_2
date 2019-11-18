import argparse
import errno
import json
import nipype
from pathlib import Path
from PipelineQC.main import qc_all
from pkg_resources import resource_filename
from pndniworkflows import utils
import warnings
import logging

from .group import group_workflow
from .participant import participant_workflow
from .utils import Labels, load_resources_file, calc_opt_resources
from . import qc
from . import logger


def get_parser():
    return _get_parser()


def main():
    args = parse_args()
    nipype.config.update_config({'execution': {'crashfile_format': 'txt'},
                                 'logging': {'workflow_level': args.loglevel,
                                             'utils_level': args.loglevel,
                                             'interface_level': args.loglevel}})
    logger.setLevel(getattr(logging, args.loglevel))
    if args.profiling_output_file:
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            nipype.config.enable_resource_monitor()
        nipype.config.set('monitoring', 'summary_file', str(args.profiling_output_file))
    nipype.logging.update_logging(nipype.config)  # needed so log level takes effect
    if args.analysis_level == 'participant':
        run_participant(args)
    elif args.analysis_level == 'group':
        run_group(args)
    elif args.analysis_level == 'qcpages':
        run_qc(args)
    elif args.analysis_level == 'create_resource_file':
        run_create_resource_file(args)
    else:
        raise ValueError(
            'Invalid value for analysis_level. How did you get here?')


def parse_args():
    args = get_parser().parse_args()
    _update_args(args)
    return args


def run_create_resource_file(args):
    out = calc_opt_resources(load_resources_file(args.profiling_input_file))
    with open(args.resource_output_file, 'w') as f:
        json.dump(out, f, indent=4)


def run_group(args):
    wf = group_workflow(args)
    wf.run(plugin=args.nipype_plugin, plugin_args=args.plugin_args)


def run_participant(args):
    wf = participant_workflow(args)
    if args.graph_output is not None:
        wf.write_graph(graph2use='hierarchical',
                       dotfilename=args.graph_output,
                       format='dot')
        return
    wf.run(plugin=args.nipype_plugin, plugin_args=args.plugin_args)


def run_qc(args):
    if args.qc_config_file is None:
        conf = qc.make_config(args.model_space,
                              args.subcortical,
                              args.subcortical_model_space,
                              args.intracranial_volume)
        if args.qc_config_file_out:
            with open(args.qc_config_file_out, 'w') as f:
                json.dump(conf, f, indent=4)
            return
    else:
        conf = args.qc_config_file
    qc_all([args.output_folder],
           args.output_folder / 'QC',
           conf,
           plugin=args.nipype_plugin,
           working_directory=args.working_directory,
           plugin_args=args.plugin_args,
           bids_validate=not args.skip_validation)


def _get_parser(for_doc=False):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'input_dataset',
        type=_resolve_existing_path,
        help='Location of `BIDS '
        '<https://bids-specification.readthedocs.io/en/stable/>`_ dataset')
    parser.add_argument('output_folder',
                        type=_resolve_existing_path,
                        help='Output directory')
    parser.add_argument('analysis_level',
                        type=str,
                        choices=['participant', 'group', 'qcpages', 'create_resource_file'],
                        help='"participant" runs the main pipeline '
                        'on each subject independently. '
                        '"group" consolidates the results. '
                        '"qcpages" uses PipelineQC to generate QC pages. '
                        '"create_resource_file" uses profiling data (--profiling_output_file) '
                        'to create a resource file with processor and memory usage for each node.')
    parser_b = parser.add_argument_group(
        'General Arguments', description='Arguments for all analysis levels (except create_resource_file)')
    parser_b.add_argument('--working_directory',
                          type=_resolve_existing_path,
                          help='(Passed to the nipype workflow)')
    parser_b.add_argument('--skip_validation',
                          action='store_true',
                          help='Skip bids validation')
    parser_b.add_argument('--nipype_plugin',
                          type=str,
                          choices=['Linear', 'MultiProc', 'Debug'],
                          default='MultiProc',
                          help='Specify the nipype workflow execution plugin. '
                          '"Linear" will aid debugging.')
    parser_b.add_argument(
        '--n_proc',
        type=int,
        help='The number of processors to use with the '
        'MultiProc plugin. If not set determine automatically.')
    parser_b.add_argument(
        '--memory_gb',
        type=float,
        help='Max memory parameter to use with the '
        'MultiProc plugin. If not set determine automatically.')
    parser_b.add_argument(
        '--profiling_output_file',
        type=Path,
        help='If set, set resource monitoring in nipype and save results to'
             'this file (JSON format).')
    parser_b.add_argument('--loglevel',
                          type=str,
                          default='INFO',
                          choices=['INFO', 'DEBUG'],
                          help='Log level passed to nipype configuration variables '
                               'workflow_level, utils_level, and interface_level.')
    parser_qcp = parser.add_argument_group(
        'Participant and QC pages arguments',
        description='Arguments for "participant" and "qcpages"')
    parser_qcp.add_argument(
        '--model_space',
        type=str,
        default='SYS808',
        help='The name of the model space. Used only for naming files.')
    parser_qcp.add_argument('--subcortical',
                            action='store_true',
                            help='Run subcortical pipeline')
    parser_qcp.add_argument('--subcortical_model_space',
                            type=str,
                            default='colin',
                            help='The name of the subcortical model space. '
                            'Only used for naming files. '
                            'REQUIRED if "--subcortical" is set.')
    parser_qcp.add_argument('--intracranial_volume',
                            action='store_true',
                            help='Calculate intracranial volume')
    # parser_g = parser.add_argument_group('group', description='Arguments for group analysis level')
    parser_p = parser.add_argument_group(
        'Participant Arguments',
        description='Arguments for participant analysis level')
    parser_p.add_argument('--participant_labels',
                          nargs='+',
                          metavar='PARTICIPANT_LABEL',
                          help='Subjects on which to run the pipeline. '
                          'If not specified, run on all.')
    parser_p.add_argument('--model',
                          type=_resolve_existing_path,
                          default=_model('SYS_808.nii.gz', for_doc=for_doc),
                          help='A model/template brain in the same space as '
                          '"--atlas" and "--tags". '
                          'Will be registered with T1w images to '
                          'map template space to native space.')
    parser_p.add_argument(
        '--atlas',
        type=_resolve_existing_path,
        default=_model('SYS808_atlas_labels_nomiddle.nii.gz', for_doc=for_doc),
        help='Atlas in model/template space subdividing the brain into lobes. '
        'This atlas will be transformed to native space and combined with the GM and WM maps.'
    )
    parser_p.add_argument(
        '--atlas_labels',
        type=_resolve_existing_path,
        help='A BIDS style label file (i.e. a tab-separated values '
        'file with "index" and "name" columns described in `BEP011 '
        '<https://docs.google.com/document/d/1YG2g4UkEio4t_STIBOqYOwneLEs1emHIX'
        'bGKynx7V0Y/edit#heading=h.g35a71g5bvrk>`_). '
        'Describes the lobes in "atlas". If not specified '
        'will look for a file with the same '
        'name ias "--atlas" but ending in "_labels.tsv".')
    parser_p.add_argument(
        '--tags',
        type=_resolve_existing_path,
        default=_model('ntags_1000_prob_90_nobg_sys808.tsv', for_doc=for_doc),
        help='A TSV file with columns "x", "y", "z", and "index" '
        '(float, float, float, int, respectively). '
        'these points are used to train the classifier. '
        'Note that if both the qform and sform of model are specified, '
        'the qform will be used, so the tags must be in those coordinates.')
    parser_p.add_argument(
        '--tag_labels',
        type=_resolve_existing_path,
        help='A label file mapping "index" in "--tags" to tissue names.')
    parser_p.add_argument('--model_brain_mask',
                          type=_resolve_existing_path,
                          default=_model('SYS808_brainmask.nii.gz',
                                         for_doc=for_doc),
                          help='Brain mask in model/template space.')
    parser_p.add_argument('--bet_frac',
                          type=float,
                          default=0.5,
                          help='Argument passed to FSL\'s BET')
    parser_p.add_argument('--bet_vertical_gradient',
                          type=float,
                          default=0.0,
                          help='Argument passed to FSL\'s BET')
    parser_p.add_argument('--inormalize_const2',
                          type=float,
                          default=[0.0, 5000.0],
                          nargs=2,
                          help='Passed to inormalize --const2 parameter')
    parser_p.add_argument('--inormalize_range',
                          type=float,
                          default=1.0,
                          help='Passed to inormalize --range parameter')
    parser_p.add_argument(
        '--debug',
        action='store_true',
        help='Set ANTs iteration count to 1 to make the workflow fast.')
    parser_p.add_argument(
        '--debug_io',
        action='store_true',
        help='Bypass main workflow to test the input/output logic.')
    parser_p.add_argument(
        '--graph_output',
        type=str,
        help='Generate a graph of the workflow and save as "--graph_output".')
    filter_parameters = [
        'filter_session',
        'filter_acquisition',
        'filter_reconstruction',
        'filter_run'
    ]
    for filter_par in filter_parameters:
        filter_par_short = filter_par.split('_')[1]
        helpstr = f'Use only T1w scans that have {filter_par_short} parameter {filter_par_short.upper()}. '
        helpstr += 'If this parameter is set without an argument, only scans '
        helpstr += f'which do not have the {filter_par_short} parameter will be selected.'
        parser_p.add_argument(f'--{filter_par}',
                              type=str,
                              help=helpstr,
                              metavar=filter_par_short.upper(),
                              nargs='?',
                              const=None,
                              default=argparse.SUPPRESS)
    parser_p.add_argument(
        '--subcortical_model',
        type=_resolve_existing_path,
        default=_model('colin27_t1_tal_lin.nii.gz', for_doc=for_doc),
        help='A model/template in the same space as "--subcortical_atlas". '
        'Will be registered with each subject. REQUIRED if "--subcortical" is set.'
    )
    parser_p.add_argument('--subcortical_atlas',
                          type=_resolve_existing_path,
                          default=_model('mask_oncolinnl_7_rs.nii.gz',
                                         for_doc=for_doc),
                          help='Atlas in delineating subcortical structures. '
                          'REQUIRED if "--subcortical" is set.')
    parser_p.add_argument(
        '--subcortical_labels',
        type=_resolve_existing_path,
        help='A label file mapping the labels in "--subcortical_atlas" '
        'to structure names')
    parser_p.add_argument('--intracranial_mask',
                          type=_resolve_existing_path,
                          default=_model('SYS808_icv.nii.gz', for_doc=for_doc),
                          help='Intracranial mask in reference space. '
                          'REQUIRED if "--intracranial_volume" is set.')
    parser_p.add_argument('--max_shear_angle', type=float, default=1e-6,
                          help='Input files are pass through forceqform '
                               'to ensure that only the qform is set. '
                               'max_shear_angle is the maximum permissible '
                               'shear in the rotation matrix if only the sform '
                               'is set. Shear angle is calculated as the '
                               'the absolute difference between the angles '
                               'between coordinates and 90 degress.')
    parser_p.add_argument('--resource_input_file',
                          type=_resolve_existing_path,
                          help='JSON file of node usage. Created using '
                               'create_resource_file command. This will set '
                               'the processor count and memory usage for each '
                               'node based on the profiling run.')
    parser_q = parser.add_argument_group(
        'QC Pages Arguments',
        description='Arguments for qcpages analysis level')
    parser_q.add_argument('--qc_config_file',
                          type=argparse.FileType('r'),
                          help='Configuration file passed to PipelineQC.')
    parser_q.add_argument('--qc_config_file_out',
                          type=Path,
                          help='Output file name for qc config (JSON)')
    parser_r = parser.add_argument_group(
        'Create resource file arguments',
        description='Arguments for the create_resource_file analysis level')
    parser_r.add_argument(
        '--profiling_input_file',
        type=_resolve_existing_path,
        help='Output from --profiling_output_file')
    parser_r.add_argument(
        '--resource_output_file',
        type=Path,
        help='Resource file to be passed to --resource_input_file')
    return parser


def _get_parser_doc():
    return _get_parser(for_doc=True)


def _get_plugin_args(args):
    plugin_args = {}
    if args.n_proc is not None:
        if args.nipype_plugin != 'MultiProc':
            raise ValueError(
                '--n_proc may only be specified with --nipype_plugin=MultiProc'
            )
        plugin_args['n_proc'] = args.n_proc
    if args.memory_gb is not None:
        if args.nipype_plugin != 'MultiProc':
            raise ValueError(
                '--memory_gp may only be specified with --nipype_plugin=MultiProc'
            )
        plugin_args['memory_gb'] = args.memory_gb
    if args.nipype_plugin == 'Debug':

        def donothing(*args):
            pass

        plugin_args['callable'] = donothing
    return plugin_args


def _model(name, for_doc=False):
    p = Path(resource_filename('TNT_pipeline_2', f'data/{name}'))
    if for_doc:
        p = Path('$INSTALLDIR', p.relative_to(Path(__file__).parent.parent))
    return p


def _resolve_existing_path(p):
    p = Path(p).resolve()
    if not p.exists():
        raise FileNotFoundError(errno.ENOENT, f'{p} does not exist')
    return p


def _update_args(args):
    args.plugin_args = _get_plugin_args(args)
    if args.analysis_level == 'participant':
        if args.subcortical:
            for req in [
                    'subcortical_model',
                    'subcortical_atlas',
                    'subcortical_model_space'
            ]:
                if getattr(args, req) is None:
                    raise ValueError(
                        'If "--subcortical" is set then {req} must be specified'
                    )
        if args.intracranial_volume:
            if args.intracranial_mask is None:
                raise ValueError(
                    'If "--intracranial_volume" is set then "intracranial_mask" must be specified'
                )
        for label_name in ['atlas', 'tissue', 'subcortical']:
            setattr(args,
                    f'{label_name}_labels',
                    Labels.from_args(args, label_name))
        setattr(
            args,
            'tissue_and_atlas_labels',
            Labels.from_labels(
                utils.combine_labels(args.tissue_labels.labels,
                                     args.atlas_labels.labels)))
        bids_filter = {}
        for filter_par in [
                'filter_session',
                'filter_acquisition',
                'filter_reconstruction',
                'filter_run'
        ]:
            if filter_par in args:
                bids_filter[filter_par.split('_')[1]] = getattr(
                    args, filter_par)
        args.bids_filter = bids_filter


if __name__ == '__main__':
    main()
