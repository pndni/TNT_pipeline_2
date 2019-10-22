import pytest
import re
from TNT_pipeline_2 import cli
from nipype.pipeline.plugins.tools import report_crash

NUMANAT = 15
NUMXFM = 2
NUMANAT_SUB = 4
NUMXFM_SUB = 2
NUMANAT_ICV = 2
NUMXFM_ICV = 0

NOARG = 'NOARG'


@pytest.fixture(scope='session')
def input_dir(tmp_path_factory):
    bd = tmp_path_factory.mktemp('bids')
    sub1 = bd / 'sub-1' / 'anat'
    sub1.mkdir(parents=True)
    (sub1 / 'sub-1_T1w.nii').write_text('sub1')
    (sub1 / 'sub-1_acq-2_T1w.nii').write_text('sub1acq2')
    (sub1 / 'sub-1_acq-3_T1w.nii').write_text('sub1acq3')
    (sub1 / 'sub-1_rec-3_T1w.nii').write_text('sub1rec3')
    (sub1 / 'sub-1_run-4_T1w.nii').write_text('sub1run4')
    (sub1 /
     'sub-1_acq-10_rec-11_run-12_T1w.nii').write_text('sub1acq10rec11run12')
    sub2 = bd / 'sub-2' / 'anat'
    sub2.mkdir(parents=True)
    (sub2 / 'sub-2_T1w.nii').write_text('sub2')
    (sub2 / 'sub-2_acq-2_T1w.nii').write_text('sub2acq2')
    (sub2 / 'sub-2_acq-3_T1w.nii').write_text('sub2acq3')
    (sub2 / 'sub-2_rec-3_T1w.nii').write_text('sub2rec3')
    (sub2 / 'sub-2_run-5_T1w.nii').write_text('sub2run5')
    (sub2 /
     'sub-2_acq-20_rec-21_run-22_T1w.nii').write_text('sub2acq20rec21run22')
    sub2sesa = bd / 'sub-2' / 'ses-a' / 'anat'
    sub2sesa.mkdir(parents=True)
    (sub2sesa / 'sub-2_ses-a_acq-2_T1w.nii').write_text('sub2sesaacq2')
    (bd / 'atlas_labels.tsv').write_text('index\tname\n1\tlobes')
    (bd / 'tag_labels.tsv').write_text('index\tname\n1\ttissue')
    (bd / 'subcortical_labels.tsv').write_text('index\tname\n1\tsubcortex')
    (bd / 'dataset_description.json'
     ).write_text('{"Name": "Test", "BIDSVersion": "1.0.0"}')
    (bd / 'dummy.txt').write_text('dummy')
    return bd


def _make_args(input_dir,
               tmp_path,
               participant_labels=None,
               debug_io=False,
               debug_plugin=False,
               subcortical=False,
               icv=False,
               **kwargs):
    cmd = [
        str(input_dir),
        str(tmp_path),
        'participant',
        '--model',
        str(input_dir / 'dummy.txt'),
        '--model_space',
        'test',
        '--atlas',
        str(input_dir / 'dummy.txt'),
        '--atlas_labels',
        str(input_dir / 'atlas_labels.tsv'),
        '--tags',
        str(input_dir / 'dummy.txt'),
        '--tag_labels',
        str(input_dir / 'tag_labels.tsv'),
        '--model_brain_mask',
        str(input_dir / 'dummy.txt'),
        '--subcortical_model_space',
        'test2',
        '--subcortical_model',
        str(input_dir / 'dummy.txt'),
        '--subcortical_atlas',
        str(input_dir / 'dummy.txt'),
        '--subcortical_labels',
        str(input_dir / 'subcortical_labels.tsv'),
        '--intracranial_mask',
        str(input_dir / 'dummy.txt')
    ]
    if subcortical:
        cmd.append('--subcortical')
    if icv:
        cmd.append('--intracranial_volume')
    if debug_io:
        cmd.append('--debug_io')
    if debug_plugin:
        cmd.append('--nipype_plugin')
        cmd.append('Debug')
    if participant_labels is not None:
        cmd.extend(['--participant_labels'] + participant_labels)
    for filter_par in [
            'filter_acquisition',
            'filter_reconstruction',
            'filter_run',
            'filter_session'
    ]:
        if filter_par in kwargs.keys():
            cmd.append(f'--{filter_par}')
            if kwargs[filter_par] is not None:
                cmd.append(kwargs[filter_par])
    return cmd


def run(*args, **kwargs):
    cmd = _make_args(*args, **kwargs)
    args = cli.get_parser().parse_args(cmd)
    cli._update_args(args)
    cli.run_participant(args)


def test_same_model_space(input_dir, tmp_path):
    cmd = _make_args(input_dir, tmp_path, debug_io=True, subcortical=True)
    ind1 = cmd.index('--model_space')
    ind2 = cmd.index('--subcortical_model_space')
    cmd[ind2 + 1] = cmd[ind1 + 1]
    args = cli.get_parser().parse_args(cmd)
    cli._update_args(args)
    cli.run_participant(args)


@pytest.mark.parametrize("icv", [False, True])
@pytest.mark.parametrize("subcort", [False, True])
@pytest.mark.parametrize(
    "filterpars,nroot,nsub2,subdirs,numsubs",
    [({
        'filter_acquisition': None,
        'filter_reconstruction': None,
        'filter_run': None
    },
      2,
      2, ['sub-1', 'sub-2'], [1, 1]),
     ({
         'participant_labels': ['1'],
         'filter_acquisition': None,
         'filter_reconstruction': None,
         'filter_run': None
     },
      1,
      None, ['sub-1'], [1]),
     ({
         'filter_acquisition': '2'
     },
      2,
      3, ['sub-1', 'sub-2', 'sub-2/ses-a'], [1, 1, 1]),
     ({
         'filter_acquisition': '2', 'filter_session': None
     },
      2,
      2, ['sub-1', 'sub-2'], [1, 1]),
     ({
         'filter_reconstruction': None, 'filter_run': None
     },
      2,
      3, ['sub-1', 'sub-2', 'sub-2/ses-a'], [3, 3, 1]),
     ({
         'filter_acquisition': None, 'filter_run': None
     },
      2,
      2, ['sub-1', 'sub-2'], [2, 2]),
     ({
         'filter_acquisition': None, 'filter_reconstruction': None
     },
      2,
      2, ['sub-1', 'sub-2'], [2, 2]),
     ({}, 2, 3, ['sub-1', 'sub-2', 'sub-2/ses-a'], [6, 6, 1])])
def test_io(input_dir,
            tmp_path,
            filterpars,
            nroot,
            nsub2,
            subdirs,
            numsubs,
            subcort,
            icv):
    run(input_dir,
        tmp_path,
        debug_io=True,
        subcortical=subcort,
        icv=icv,
        **filterpars)
    assert len(list(tmp_path.iterdir())) == nroot
    if nsub2 is not None:
        assert len(list((tmp_path / 'sub-2').iterdir())) == nsub2
    numanat = NUMANAT
    numxfm = NUMXFM
    if subcort:
        numanat += NUMANAT_SUB
        numxfm += NUMXFM_SUB
    if icv:
        numanat += NUMANAT_ICV
        numxfm += NUMXFM_ICV
    for sub, nsubs in zip(subdirs, numsubs):
        assert len(list(
            (tmp_path / sub / 'anat').iterdir())) == numanat * nsubs
        assert len(list((tmp_path / sub / 'xfm').iterdir())) == numxfm * nsubs
        for ftmp in (tmp_path / sub / 'anat').iterdir():
            if ftmp.name[-10:] != 'labels.tsv':
                m = re.search(
                    'sub-[0-9]*(_ses-[a-z]*)?(_acq-[0-9]*)?(_rec-[0-9]*)?(_run-[0-9]*)?',
                    ftmp.name)
                cmpstr = ftmp.name[m.start():m.end()].replace('-', '').replace(
                    '_', '')
                assert ftmp.read_text() == cmpstr
            else:
                with open(ftmp, 'r', newline='') as flabel:
                    if 'tissuelobes' in ftmp.name:
                        assert flabel.read(
                        ) == 'index\tname\r\n1\ttissue+lobes\r\n'
                    elif 'tissue' in ftmp.name:
                        assert flabel.read() == 'index\tname\r\n1\ttissue\r\n'
                    elif 'lobes' in ftmp.name:
                        assert flabel.read() == 'index\tname\r\n1\tlobes\r\n'
                    elif 'subcortex' in ftmp.name:
                        assert flabel.read(
                        ) == 'index\tname\r\n1\tsubcortex\r\n'
                    else:
                        raise RuntimeError()


@pytest.mark.parametrize('icv', [False, True])
@pytest.mark.parametrize('subcortical', [False, True])
def test_debug_plugin(input_dir, tmp_path, subcortical, icv):
    run(input_dir,
        tmp_path,
        debug_plugin=True,
        subcortical=subcortical,
        icv=icv)


class Acq10Exception(Exception):
    pass


def _crash_on_acq_10(node, graph):
    if 'acquisition-10' in node.fullname:
        try:
            raise Acq10Exception
        except Exception as e:
            report_crash(node)
            raise e


def test_crash(input_dir, tmp_path):
    args = cli.get_parser().parse_args(
        _make_args(input_dir, tmp_path, debug_plugin=True))
    cli._update_args(args)
    args.plugin_args = {'callable': _crash_on_acq_10}
    with pytest.raises(Acq10Exception):
        cli.run_participant(args)
    crashpaths = list((tmp_path / 'logs').iterdir())
    assert len(crashpaths) == 1
    for crashpath in crashpaths:
        contents = list(crashpath.iterdir())
        assert len(contents) == 1
        assert crashpath.name == 'sub-1'
        assert contents[0].name == 'sub-1_acq-10_rec-11_run-12'
        assert len(list(contents[0].iterdir())) == 1
