import pytest
from pndniworkflows.utils import write_labels
from TNT_pipeline_2 import cli


@pytest.fixture
def args(tmp_path):
    (tmp_path / 'tags.txt').write_text('tags')
    write_labels(tmp_path / 'tags_labels.tsv', [{'index': 1, 'name': 'GM'},
                                                {'index': 2, 'name': 'WM'}])
    (tmp_path / 'atlas.nii.gz').write_text('atlas')
    write_labels(tmp_path / 'atlas_labels.tsv', [{'index': 1, 'name': 'frontal'},
                                                 {'index': 2, 'name': 'temporal'},
                                                 {'index': 3, 'name': 'occipital'}])

    class Namespace(object):
        pass

    args = Namespace()
    args.tags = tmp_path / 'tags.txt'
    args.atlas = tmp_path / 'atlas.nii.gz'
    return args


@pytest.mark.parametrize('explicit', [True, False])
def test_Labels_from_args(args, explicit):
    if explicit:
        args.tag_labels = args.tags.parent / 'tags_labels.tsv'
        args.atlas_labels = args.atlas.parent / 'atlas_labels.tsv'
    else:
        args.tag_labels = None
        args.atlas_labels = None
    tissue = cli.Labels.from_args(args, 'tissue')
    atlas = cli.Labels.from_args(args, 'atlas')
    assert tissue.string == 'index\tname\r\n1\tGM\r\n2\tWM\r\n'
    assert atlas.string == 'index\tname\r\n1\tfrontal\r\n2\ttemporal\r\n3\toccipital\r\n'


def test_Labels_from_labels():
    tissue = cli.Labels.from_labels([{'index': 1, 'name': 'GM'},
                                     {'index': 2, 'name': 'WM'}])
    assert tissue.string == 'index\tname\r\n1\tGM\r\n2\tWM\r\n'


def test_get_label_file(tmp_path):
    testfile = tmp_path / 'image.nii.gz'
    with pytest.raises(ValueError):
        cli.Labels._get_label_file(testfile, 'teststr')
    labelfile = tmp_path / 'image_labels.tsv'
    labelfile.write_text('test')
    out = cli.Labels._get_label_file(testfile, 'teststr')
    assert labelfile == out
