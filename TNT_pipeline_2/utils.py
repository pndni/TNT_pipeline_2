import errno
import io
from pathlib import Path
from pndniworkflows import utils


class Labels(object):
    def __init__(self, *, labels, string):
        self.labels = labels
        self.string = string

    @classmethod
    def from_args(cls, args, name):
        if name == 'atlas':
            label_arg = 'atlas_labels'
            base_arg = 'atlas'
        elif name == 'tissue':
            label_arg = 'tag_labels'
            base_arg = 'tags'
        elif name == 'subcortical':
            label_arg = 'subcortical_labels'
            base_arg = 'subcortical_atlas'
        else:
            raise ValueError('Unsupported label type')

        if name == 'subcortical' and not args.subcortical:
            return cls(labels=None, string=None)
        filename = getattr(args, label_arg)
        if filename is None:
            filename = cls._get_label_file(getattr(args, base_arg),
                                           f'--{label_arg}')
        labels = utils.read_labels(filename)
        return cls.from_labels(labels)

    @classmethod
    def from_labels(cls, labels):
        string_ = cls._labels_to_str(labels)
        return cls(labels=labels, string=string_)

    @staticmethod
    def _get_label_file(basefile, argstr):
        suffixes = ''.join(basefile.suffixes)
        labelfile = Path(basefile.parent,
                         basefile.name[:-len(suffixes)] + '_labels.tsv')
        if not labelfile.exists():
            raise FileNotFoundError(
                errno.ENOENT,
                f'No label file for {basefile} specified and '
                f'{labelfile} does not exist. Use {argstr} to '
                'specify a label file.')
        return labelfile

    @staticmethod
    def _labels_to_str(labels):
        s = io.StringIO(newline='')
        utils.write_labels(s, labels)
        s.seek(0)
        return s.read()


def _update_workdir(wf, workdir):
    if workdir is None:
        return
    if not workdir.exists():
        raise FileNotFoundError(
            errno.ENOENT,
            'Specified working directory ({workdir}) does not exist')
    wf.base_dir = str(workdir)
