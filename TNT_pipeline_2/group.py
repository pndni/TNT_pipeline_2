from nipype.pipeline import engine as pe
from pndniworkflows.interfaces.io import CombineStats
from nipype.interfaces.utility import Rename


def group_workflow(out_dir, validate):
    groupdir = out_dir / 'group'
    groupdir.mkdir(exist_ok=True)
    outfile = groupdir / 'group.tsv'
    # if outfile.exists():
    #     raise FileExistsError(f'{outfile} exists')
    wf = pe.Workflow('group')
    combine = pe.Node(CombineStats(bids_dir=str(out_dir),
                                   validate=validate,
                                   row_keys=['subject', 'session', 'acquisition', 'reconstruction', 'rec'],
                                   invariants={'datatype': 'anat', 'extension': 'tsv'},
                                   index='name',
                                   ignore={'index'}),
                      'combine')
    write = pe.Node(Rename(format_string=str(outfile)), 'write')
    wf.connect(combine, 'out_tsv', write, 'in_file')

    return wf
