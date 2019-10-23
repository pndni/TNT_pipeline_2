import subprocess
from pkg_resources import resource_filename
from shutil import copyfile


def test_cli(tmp_path):
    t1 = resource_filename('TNT_pipeline_2', f'data/SYS_808.nii.gz')
    indir = tmp_path / 'in'
    t1bids = indir / 'sub-1' / 'anat' / 'sub-1_T1w.nii.gz'
    t1bids.parent.mkdir(parents=True)
    copyfile(t1, t1bids)
    outdir = tmp_path / 'out'
    outdir.mkdir()
    cmd = ['TNT_pipeline_2', str(indir), str(outdir), 'participant',
           '--subcortical', '--intracranial_volume', '--skip_validation', '--debug']
    subprocess.check_call(cmd)
    cmd = ['TNT_pipeline_2', str(indir), str(outdir), 'qcpages',
           '--subcortical', '--intracranial_volume']
    subprocess.check_call(cmd)
