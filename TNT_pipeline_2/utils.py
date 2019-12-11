import errno
import io
from pathlib import Path
from pndniworkflows import utils
import json
import numpy as np


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


def read_json(fname):
    with open(fname, 'r') as f:
        return json.load(f)


def write_json(obj, fname):
    with open(fname, 'w') as f:
        json.dump(obj, f, indent=4)


def load_resources_file(fname):
    resources = read_json(fname)
    keys = ['rss_GiB', 'vms_GiB', 'cpus', 'time']
    length = len(resources['name'])
    for k in keys:
        if len(resources[k]) != length:
            raise RuntimeError(f'Length of "{k}" in {fname} does not match length of "name"')
    out = {}
    for i in range(length):
        name = resources['name'][i]
        if name not in out:
            out[name] = {}
        for k in keys:
            if k not in out[name]:
                out[name][k] = []
            out[name][k].append(float(resources[k][i]))
    return out


def calc_opt_resources(resources, mintime=1.0, mininterval=0.1):
    out = {}
    for name, data in resources.items():
        out[name] = {}
        deltatimes = np.diff(data['time'])
        cpus = np.array(data['cpus'][1:])
        inds = deltatimes > mininterval
        if np.any(inds):
            cpumax = np.max(cpus[inds])
        else:
            cpumax = None
        totaltime = data['time'][-1] - data['time'][0]
        if totaltime < mintime or cpumax is None:
            ncpu = 1
        else:
            ncpu = max(int(np.ceil(cpumax / 100.0)), 1)
        out[name]['ncpu'] = ncpu
        out[name]['cpumax'] = cpumax
        out[name]['mem'] = np.max(data['rss_GiB'])
        out[name]['time'] = totaltime
    out2 = {}
    for name, data in out.items():
        nameadj = adjust_node_name(name)
        if nameadj not in out2:
            out2[nameadj] = data
        else:
            for k in data.keys():
                if data[k] is not None:
                    if out2[nameadj][k] is None or data[k] > out2[nameadj][k]:
                        out2[nameadj][k] = data[k]
    return out2


def adjust_node_name(name):
    namesplit = name.split('.')
    if namesplit[0] == 'participant':
        T1 = namesplit.pop(1)
        if T1[:3] != 'T1_':
            return name
        nameadj = '.'.join(namesplit)
    else:
        nameadj = name
    return nameadj
