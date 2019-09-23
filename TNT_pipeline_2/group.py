from nipype.pipeline import engine as pe
from pndniworkflows.interfaces.io import CombineStats
from nipype.interfaces.utility import Rename
from .utils import _update_workdir


def group_workflow(args):
    groupdir = args.out_dir / 'group'
    groupdir.mkdir(exist_ok=True)
    outfile = groupdir / 'group.tsv'
    # if outfile.exists():
    #     raise FileExistsError(f'{outfile} exists')
    wf = pe.Workflow('group')
    combine = pe.Node(CombineStats(bids_dir=str(args.out_dir),
                                   validate=not args.skip_validation,
                                   row_keys=['subject', 'session', 'acquisition', 'reconstruction', 'rec'],
                                   invariants={'datatype': 'anat', 'extension': 'tsv'},
                                   index='name',
                                   ignore={'index'}),
                      'combine')
    write = pe.Node(Rename(format_string=str(outfile)), 'write')
    wf.connect(combine, 'out_tsv', write, 'in_file')
    _update_workdir(wf, args.working_directory)
    return wf
