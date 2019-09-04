import pytest
import subprocess
import re


NUMANAT = 13
NUMXFM = 2

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
    (sub1 / 'sub-1_acq-10_rec-11_run-12_T1w.nii').write_text('sub1acq10rec11run12')
    sub2 = bd / 'sub-2' / 'anat'
    sub2.mkdir(parents=True)
    (sub2 / 'sub-2_T1w.nii').write_text('sub2')
    (sub2 / 'sub-2_acq-2_T1w.nii').write_text('sub2acq2')
    (sub2 / 'sub-2_acq-3_T1w.nii').write_text('sub2acq3')
    (sub2 / 'sub-2_rec-3_T1w.nii').write_text('sub2rec3')
    (sub2 / 'sub-2_run-5_T1w.nii').write_text('sub2run5')
    (sub2 / 'sub-2_acq-20_rec-21_run-22_T1w.nii').write_text('sub2acq20rec21run22')
    (bd / 'labels.tsv').write_text('index\tname\n1\tone')
    (bd / 'dataset_description.json').write_text('{"Name": "Test", "BIDSVersion": "1.0.0"}')
    return bd


def run(input_dir, tmp_path, participant_labels=None, **kwargs):
    cmd = ['python', 'TNT_pipeline_2/pipeline.py',
           str(input_dir),
           str(tmp_path),
           'participant',
           '--model', 'None',
           '--model_space', 'test',
           '--atlas', 'None',
           '--atlas_labels', str(input_dir / 'labels.tsv'),
           '--tags', 'None',
           '--tag_labels', str(input_dir / 'labels.tsv'),
           '--model_brain_mask', 'None',
           '--debug_io']
    if participant_labels is not None:
        cmd.extend(['--participant_labels'] + participant_labels)
    for filter_par in ['filter_acquisition', 'filter_reconstruction', 'filter_run']:
        if filter_par in kwargs.keys():
            cmd.append(f'--{filter_par}')
            if kwargs[filter_par] is not None:
                cmd.append(kwargs[filter_par])
    subprocess.check_call(cmd)


def test_basic(input_dir, tmp_path):
    run(input_dir, tmp_path, filter_acquisition=None, filter_reconstruction=None, filter_run=None)
    assert len(list(tmp_path.iterdir())) == 2
    for sub in ['sub-1', 'sub-2']:
        assert len(list((tmp_path / sub / 'anat').iterdir())) == NUMANAT
        assert len(list((tmp_path / sub / 'xfm').iterdir())) == NUMXFM
        for ftmp in (tmp_path / sub / 'anat').iterdir():
            if ftmp.name[-10:] != 'labels.tsv':
                assert ftmp.read_text() == sub.replace('-', '')


def test_sub1(input_dir, tmp_path):
    run(input_dir, tmp_path, participant_labels=['1'], filter_acquisition=None, filter_reconstruction=None, filter_run=None)
    assert len(list(tmp_path.iterdir())) == 1
    for sub in ['sub-1']:
        assert len(list((tmp_path / sub / 'anat').iterdir())) == NUMANAT
        assert len(list((tmp_path / sub / 'xfm').iterdir())) == NUMXFM
        for ftmp in (tmp_path / sub / 'anat').iterdir():
            if ftmp.name[-10:] != 'labels.tsv':
                assert ftmp.read_text() == sub.replace('-', '')


def test_acq2(input_dir, tmp_path):
    run(input_dir, tmp_path, filter_acquisition='2')
    assert len(list(tmp_path.iterdir())) == 2
    for sub in ['sub-1', 'sub-2']:
        assert len(list((tmp_path / sub / 'anat').iterdir())) == NUMANAT
        assert len(list((tmp_path / sub / 'xfm').iterdir())) == NUMXFM
        for ftmp in (tmp_path / sub / 'anat').iterdir():
            assert 'acq-2' in ftmp.name
            if ftmp.name[-10:] != 'labels.tsv':
                assert ftmp.read_text() == sub.replace('-', '') + 'acq2'


def test_acqall(input_dir, tmp_path):
    run(input_dir, tmp_path, filter_reconstruction=None, filter_run=None)
    assert len(list(tmp_path.iterdir())) == 2
    for sub in ['sub-1', 'sub-2']:
        assert len(list((tmp_path / sub / 'anat').iterdir())) == NUMANAT * 3
        assert len(list((tmp_path / sub / 'xfm').iterdir())) == NUMXFM * 3
        for ftmp in (tmp_path / sub / 'anat').iterdir():
            if ftmp.name[-10:] != 'labels.tsv':
                m = re.search('sub-[0-9]*(_acq-[0-9]*)?(_rec-[0-9]*)?(_run-[0-9]*)?', ftmp.name)
                cmpstr = ftmp.name[m.start():m.end()].replace('-', '').replace('_', '')
                assert ftmp.read_text() == cmpstr


def test_recall(input_dir, tmp_path):
    run(input_dir, tmp_path, filter_acquisition=None, filter_run=None)
    assert len(list(tmp_path.iterdir())) == 2
    for sub in ['sub-1', 'sub-2']:
        assert len(list((tmp_path / sub / 'anat').iterdir())) == NUMANAT * 2
        assert len(list((tmp_path / sub / 'xfm').iterdir())) == NUMXFM * 2
        for ftmp in (tmp_path / sub / 'anat').iterdir():
            if ftmp.name[-10:] != 'labels.tsv':
                m = re.search('sub-[0-9]*(_acq-[0-9]*)?(_rec-[0-9]*)?(_run-[0-9]*)?', ftmp.name)
                cmpstr = ftmp.name[m.start():m.end()].replace('-', '').replace('_', '')
                assert ftmp.read_text() == cmpstr


def test_runall(input_dir, tmp_path):
    run(input_dir, tmp_path, filter_acquisition=None, filter_reconstruction=None)
    assert len(list(tmp_path.iterdir())) == 2
    for sub in ['sub-1', 'sub-2']:
        assert len(list((tmp_path / sub / 'anat').iterdir())) == NUMANAT * 2
        assert len(list((tmp_path / sub / 'xfm').iterdir())) == NUMXFM * 2
        for ftmp in (tmp_path / sub / 'anat').iterdir():
            if ftmp.name[-10:] != 'labels.tsv':
                m = re.search('sub-[0-9]*(_acq-[0-9]*)?(_rec-[0-9]*)?(_run-[0-9]*)?', ftmp.name)
                cmpstr = ftmp.name[m.start():m.end()].replace('-', '').replace('_', '')
                assert ftmp.read_text() == cmpstr


def test_all(input_dir, tmp_path):
    run(input_dir, tmp_path)
    assert len(list(tmp_path.iterdir())) == 2
    for sub in ['sub-1', 'sub-2']:
        assert len(list((tmp_path / sub / 'anat').iterdir())) == NUMANAT * 6
        assert len(list((tmp_path / sub / 'xfm').iterdir())) == NUMXFM * 6
        for ftmp in (tmp_path / sub / 'anat').iterdir():
            if ftmp.name[-10:] != 'labels.tsv':
                m = re.search('sub-[0-9]*(_acq-[0-9]*)?(_rec-[0-9]*)?(_run-[0-9]*)?', ftmp.name)
                cmpstr = ftmp.name[m.start():m.end()].replace('-', '').replace('_', '')
                assert ftmp.read_text() == cmpstr
