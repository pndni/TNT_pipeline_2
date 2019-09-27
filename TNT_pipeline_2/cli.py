import argparse
import errno
from nipype import config
from pathlib import Path
from PipelineQC.main import qc_all
from pkg_resources import resource_filename
from pndniworkflows import utils

from .group import group_workflow
from .participant import participant_workflow
from .utils import Labels
from . import qc

PIPELINE_NAME = 'Toronto Pipeline'


def get_parser():
    return _get_parser()


def main():
    args = parse_args()
    config.update_config({'execution': {'crashfile_format': 'txt'}})
    if args.analysis_level == 'participant':
        run_participant(args)
    elif args.analysis_level == 'group':
        run_group(args)
    elif args.analysis_level == 'qcpages':
        run_qc(args)
    else:
        raise ValueError(
            'Invalid value for analysis_level. How did you get here?')


def parse_args():
    args = get_parser().parse_args()
    _update_args(args)
    return args


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
        conf = qc.make_config(args.model.name,
                              args.model_space,
                              args.subcortical,
                              args.subcortical_model_space,
                              args.intracranial_volume)
    else:
        conf = args.qc_config_file
    qc_all([args.input_dataset, args.output_folder, args.model.parent],
           args.output_folder / 'QC',
           conf,
           plugin=args.nipype_plugin,
           working_directory=args.working_directory)


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
                        choices=['participant', 'group', 'qcpages'],
                        help='"participant" runs the main pipeline '
                        'on each subject independently. '
                        '"group" consolidates the results. '
                        '"qcpages" uses PipelineQC to generate QC pages.')
    parser_b = parser.add_argument_group(
        'General Arguments', description='Arguments for all analysis levels')
    parser_b.add_argument('--working_directory',
                          type=_resolve_existing_path,
                          help='(Passed to the nipype workflow)')
    parser_b.add_argument('--skip_validation',
                          action='store_true',
                          help='Skip bids validation')
    parser_b.add_argument('--nipype_plugin',
                          type=str,
                          choices=['Linear', 'MultiProc', 'Debug'],
                          help='Specify the nipype workflow execution plugin. '
                          '"Linear" will aid debugging.')
    parser_b.add_argument(
        '--n_proc',
        type=int,
        help='The number of processors to use with the '
        'MultiProc plugin. If not set determine automatically.')
    parser_pq = parser.add_argument_group(
        description='Arguments for participant and qcpages analysis levels')
    parser_pq.add_argument('--model',
                           type=_resolve_existing_path,
                           default=_model('SYS_808.nii.gz', for_doc=for_doc),
                           help='A model/template brain in the same space as '
                           '"--atlas" and "--tags". '
                           'Will be registered with T1w images to '
                           'map template space to native space.')
    # parser_g = parser.add_argument_group('group', description='Arguments for group analysis level')
    parser_p = parser.add_argument_group(
        'Participant Arguments',
        description='Arguments for participant analysis level')
    parser_p.add_argument('--participant_labels',
                          nargs='+',
                          metavar='PARTICIPANT_LABEL',
                          help='Subjects on which to run the pipeline. '
                          'If not specified, run on all.')
    parser_p.add_argument(
        '--model_space',
        type=str,
        default='SYS808',
        help='The name of the model space. Used only for naming files.')
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
        'these points are used to train the classifier.')
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
    parser_p.add_argument('--subcortical',
                          action='store_true',
                          help='Run subcortical pipeline')
    parser_p.add_argument(
        '--subcortical_model',
        type=_resolve_existing_path,
        default=_model('colin27_t1_tal_lin.nii.gz', for_doc=for_doc),
        help='A model/template in the same space as "--subcortical_atlas". '
        'Will be registered with each subject. REQUIRED if "--subcortical" is set.'
    )
    parser_p.add_argument('--subcortical_model_space',
                          type=str,
                          default='colin',
                          help='The name of the subcortical model space. '
                          'Only used for naming files. '
                          'REQUIRED if "--subcortical" is set.')
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
    parser_p.add_argument('--intracranial_volume',
                          action='store_true',
                          help='Calculate intracranial volume')
    parser_p.add_argument('--intracranial_mask',
                          type=_resolve_existing_path,
                          default=_model('SYS808_icv.nii.gz', for_doc=for_doc),
                          help='Intracranial mask in reference space. '
                          'REQUIRED if "--intracranial_volume" is set.')
    parser_q = parser.add_argument_group(
        'QC Pages Arguments',
        description='Arguments for qcpages analysis level')
    parser_q.add_argument('--qc_config_file',
                          type=argparse.FileType('r'),
                          help='Configuration file passed to PipelineQC.')
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
