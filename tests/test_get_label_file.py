import pytest
from TNT_pipeline_2.pipeline import _get_label_file



def test_get_label_file(tmp_path):
    testfile = tmp_path / 'image.nii.gz'
    with pytest.raises(ValueError):
        _get_label_file(testfile, 'teststr')
    labelfile = tmp_path / 'image_labels.tsv'
    labelfile.write_text('test')
    out = _get_label_file(testfile, 'teststr')
    assert labelfile == out
