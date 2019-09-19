from nipype.pipeline import engine as pe
from nipype import IdentityInterface, Rename
from pndniworkflows.interfaces import io
from pndniworkflows.utils import first_nonunique
from pathlib import Path


def get_outputinfo(model_space, subcortical, subcortical_model_space):
    outputinfo = {}
    outputinfo['nu_bet'] = {'skullstripped': 'true',
                            'desc': 'nucor',
                            'suffix': 'T1w',
                            'extension': 'nii.gz'}
    outputinfo['normalized'] = {'skullstripped': 'true',
                                'desc': 'normalized',
                                'suffix': 'T1w',
                                'extension': 'nii.gz'}
    outputinfo['brain_mask'] = {'desc': 'brain',
                                'suffix': 'mask',
                                'space': 'T1w',
                                'extension': 'nii.gz'}
    outputinfo['transform'] = {'from_': model_space,
                               'to': 'T1w',
                               'suffix': 'xfm',
                               'mode': 'image',
                               'extension': 'h5'}
    outputinfo['inverse_transform'] = {'to': model_space,
                                       'from_': 'T1w',
                                       'suffix': 'xfm',
                                       'mode': 'image',
                                       'extension': 'h5'}
    outputinfo['warped_model'] = {'space': 'T1w',
                                  'suffix': 'T1w',
                                  'map_': model_space,
                                  'extension': 'nii.gz'}
    outputinfo['transformed_model_brain_mask'] = {'space': 'T1w',
                                                  'suffix': 'mask',
                                                  'map_': model_space,
                                                  'desc': 'brain',
                                                  'extension': 'nii.gz'}
    outputinfo['classified'] = {'suffix': 'dseg',
                                'space': 'T1w',
                                'desc': 'tissue',
                                'extension': 'nii.gz'}
    outputinfo['transformed_atlas'] = {'suffix': 'dseg',
                                       'space': 'T1w',
                                       'desc': 'lobes',
                                       'extension': 'nii.gz'}
    outputinfo['segmented'] = {'suffix': 'dseg',
                               'space': 'T1w',
                               'desc': 'tissue+lobes',
                               'extension': 'nii.gz'}
    outputinfo['features'] = {'suffix': 'features',
                              'space': 'T1w',
                              'desc': 'tissue',
                              'extension': 'txt'}
    outputinfo['stats'] = {'suffix': 'stats', 'desc': 'tissue+lobes', 'extension': 'tsv'}
    outputinfo['brainstats'] = {'suffix': 'stats', 'desc': 'brain', 'extension': 'tsv'}
    if subcortical:
        outputinfo['subcortical_transform'] = {'to': 'T1w',
                                               'from_': subcortical_model_space,
                                               'suffix': 'xfm',
                                               'desc': 'subcortex',
                                               'mode': 'image',
                                               'extension': 'h5'}
        outputinfo['subcortical_inverse_transform'] = {'from_': 'T1w',
                                                       'to': subcortical_model_space,
                                                       'suffix': 'xfm',
                                                       'desc': 'subcortex',
                                                       'mode': 'image',
                                                       'extension': 'h5'}
        outputinfo['warped_subcortical_model'] = {'space': 'T1w',
                                                  'suffix': 'T1w',
                                                  'map_': subcortical_model_space,
                                                  'desc': 'subcortex',
                                                  'extension': 'nii.gz'}
        outputinfo['native_subcortical_atlas'] = {'suffix': 'dseg',
                                                  'space': 'T1w',
                                                  'desc': 'subcortex',
                                                  'extension': 'nii.gz'}
        outputinfo['subcortical_stats'] = {'suffix': 'stats', 'desc': 'subcortex', 'extension': 'tsv'}
    return outputinfo


def io_out_workflow(bidslayout, entities, output_folder, model_space,
                    atlas_labels_str, tissue_labels_str, tissue_and_atlas_labels_str,
                    subcortical=False, subcortical_model_space=None):

    if subcortical and subcortical_model_space is None:
        raise ValueError('If subcortical is True then subcortical_model_space cannot be None')
    wf = pe.Workflow(name='io_out')
    outputinfo = get_outputinfo(model_space, subcortical, subcortical_model_space)
    inputspec = pe.Node(IdentityInterface(fields=list(outputinfo.keys())), 'inputspec')
    outputfilenames = {}
    for sourcename, bidsinfo in outputinfo.items():
        tmppath = bidslayout.build_path({**bidsinfo, **entities}, strict=True)
        if tmppath is None:
            raise RuntimeError('Unable to build path with {}'.format({**bidsinfo, **entities}))
        tmppath = Path(bidslayout.root, tmppath).resolve()
        tmppath.parent.mkdir(exist_ok=True, parents=True)
        outputfilenames[sourcename] = str(tmppath)
    outputlabels = {}
    for sourcename, label_str in zip(['classified', 'transformed_atlas', 'segmented', 'features'],
                                     [tissue_labels_str, atlas_labels_str, tissue_and_atlas_labels_str, tissue_labels_str]):
        tmpparams = outputinfo[sourcename].copy()
        tmpparams['extension'] = 'tsv'
        tmplabelpath = bidslayout.build_path({**tmpparams, **entities}, strict=True)
        if tmplabelpath is None:
            raise RuntimeError('Unable to build path with {}'.format({**tmpparams, **entities}))
        outputlabels[sourcename] = (str(Path(bidslayout.root, tmplabelpath).resolve()),
                                    tissue_labels_str)
    duplicate = first_nonunique(list(outputfilenames.values()) + list(outputlabels.values()))
    if duplicate is not None:
        raise RuntimeError('Duplicate output files detected! {}'.format(duplicate))
    for sourcename in outputinfo.keys():
        node = pe.Node(Rename(format_string=outputfilenames[sourcename]), name='write' + sourcename)
        wf.connect(inputspec, sourcename, node, 'in_file')
        if sourcename in outputlabels:
            labelnode = pe.Node(io.WriteFile(out_file=outputlabels[sourcename][0],
                                             string=outputlabels[sourcename][1],
                                             newline=''), 'write' + sourcename + 'label')
            wf.add_nodes([labelnode])
    return wf
