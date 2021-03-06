from nipype.pipeline import engine as pe
from nipype import IdentityInterface
from nipype.interfaces.io import ExportFile
from pndniworkflows.interfaces import io
from pndniworkflows.utils import first_nonunique
from pathlib import Path


def get_outputinfo(model_space,
                   subcortical,
                   subcortical_model_space,
                   intracranial_volume):
    outputinfo = {}
    outputinfo['T1'] = {
        'suffix': 'T1w',
        'extension': 'nii.gz'
    }
    # outputinfo['model'] = {
    #     'space': model_space,
    #     'desc': model_space,
    #     'suffix': 'T1w',
    #     'extension': 'nii.gz'
    # }
    # outputinfo['atlas'] = {
    #     'space': model_space,
    #     'suffix': 'dseg',
    #     'desc': f'{model_space}lobes',
    #     'extension': 'nii.gz'
    # }
    # outputinfo['model_brain_mask'] = {
    #     'space': model_space,
    #     'suffix': 'mask',
    #     'desc': f'{model_space}brain',
    #     'extension': 'nii.gz'
    # }
    outputinfo['nu'] = {
        'skullstripped': 'false',
        'desc': 'nucor',
        'suffix': 'T1w',
        'extension': 'nii.gz'
    }
    outputinfo['normalized'] = {
        'skullstripped': 'false',
        'desc': 'normalized',
        'suffix': 'T1w',
        'extension': 'nii.gz'
    }
    outputinfo['brain_mask'] = {
        'desc': 'brain',
        'suffix': 'mask',
        'space': 'T1w',
        'extension': 'nii.gz'
    }
    outputinfo['linear_transform'] = {
        'from': model_space,
        'to': 'T1w',
        'suffix': 'xfm',
        'mode': 'image',
        'extension': 'h5',
        'desc': 'linear'
    }
    outputinfo['transform'] = {
        'from': model_space,
        'to': 'T1w',
        'suffix': 'xfm',
        'mode': 'image',
        'extension': 'h5'
    }
    outputinfo['inverse_transform'] = {
        'to': model_space,
        'from': 'T1w',
        'suffix': 'xfm',
        'mode': 'image',
        'extension': 'h5'
    }
    outputinfo['warped_model'] = {
        'space': 'T1w',
        'suffix': 'T1w',
        'desc': model_space,
        'extension': 'nii.gz'
    }
    outputinfo['transformed_model_brain_mask'] = {
        'space': 'T1w',
        'suffix': 'mask',
        'desc': f'{model_space}brain',
        'extension': 'nii.gz'
    }
    outputinfo['classified'] = {
        'suffix': 'dseg',
        'space': 'T1w',
        'desc': 'tissue',
        'extension': 'nii.gz'
    }
    outputinfo['transformed_atlas'] = {
        'suffix': 'dseg',
        'space': 'T1w',
        'desc': f'{model_space}lobes',
        'extension': 'nii.gz'
    }
    outputinfo['segmented'] = {
        'suffix': 'dseg',
        'space': 'T1w',
        'desc': 'tissuelobes',
        'extension': 'nii.gz'
    }
    outputinfo['features'] = {
        'suffix': 'features',
        'space': 'T1w',
        'desc': 'tissue',
        'extension': 'tsv'
    }
    outputinfo['stats'] = {
        'suffix': 'stats', 'desc': 'tissuelobes', 'extension': 'tsv'
    }
    outputinfo['brainstats'] = {
        'suffix': 'stats', 'desc': 'brain', 'extension': 'tsv'
    }
    if subcortical:
        outputinfo['subcortical_transform'] = {
            'to': 'T1w',
            'from': subcortical_model_space,
            'suffix': 'xfm',
            'desc': 'subcortex',
            'mode': 'image',
            'extension': 'h5'
        }
        outputinfo['subcortical_linear_transform'] = {
            'to': 'T1w',
            'from': subcortical_model_space,
            'suffix': 'xfm',
            'desc': 'subcortexlinear',
            'mode': 'image',
            'extension': 'h5'
        }
        outputinfo['subcortical_inverse_transform'] = {
            'from': 'T1w',
            'to': subcortical_model_space,
            'suffix': 'xfm',
            'desc': 'subcortex',
            'mode': 'image',
            'extension': 'h5'
        }
        # outputinfo['subcortical_model'] = {
        #     'space': subcortical_model_space,
        #     'desc': f'subcortex{subcortical_model_space}',
        #     'suffix': 'T1w',
        #     'extension': 'nii.gz'
        # }
        # outputinfo['subcortical_atlas'] = {
        #     'space': subcortical_model_space,
        #     'suffix': 'dseg',
        #     'desc': f'subcortex{subcortical_model_space}atlas',
        #     'extension': 'nii.gz'
        # }
        outputinfo['warped_subcortical_model'] = {
            'space': 'T1w',
            'suffix': 'T1w',
            'desc': f'subcortex{subcortical_model_space}',
            'extension': 'nii.gz'
        }
        outputinfo['native_subcortical_atlas'] = {
            'suffix': 'dseg',
            'space': 'T1w',
            'desc': f'subcortex{subcortical_model_space}atlas',
            'extension': 'nii.gz'
        }
        outputinfo['subcortical_stats'] = {
            'suffix': 'stats', 'desc': 'subcortex', 'extension': 'tsv'
        }
    if intracranial_volume:
        # outputinfo['intracranial_mask'] = {
        #     'suffix': 'mask',
        #     'space': model_space,
        #     'desc': f'{model_space}ICV',
        #     'extension': 'nii.gz'
        # }
        outputinfo['native_intracranial_mask'] = {
            'suffix': 'mask',
            'space': 'T1w',
            'desc': f'{model_space}ICV',
            'extension': 'nii.gz'
        }
        outputinfo['icv_stats'] = {
            'suffix': 'stats', 'desc': 'ICV', 'extension': 'tsv'
        }
    return outputinfo


def io_out_workflow(bidslayout,
                    entities,
                    output_folder,
                    model_space,
                    atlas_labels_str,
                    tissue_labels_str,
                    tissue_and_atlas_labels_str,
                    subcortical=False,
                    subcortical_model_space=None,
                    subcortical_labels_str=None,
                    intracranial_volume=False,
                    debug=False):

    if subcortical and (subcortical_model_space is None
                        or subcortical_labels_str is None):
        raise ValueError(
            'If subcortical is True then subcortical_model_space and subcortical_labels_str cannot be None'
        )
    wf = pe.Workflow(name='io_out')
    outputinfo = get_outputinfo(model_space,
                                subcortical,
                                subcortical_model_space,
                                intracranial_volume)
    inputspec = pe.Node(IdentityInterface(fields=list(outputinfo.keys())),
                        'inputspec')
    outputfilenames = {}
    for sourcename, bidsinfo in outputinfo.items():
        tmppath = bidslayout.build_path({
            **bidsinfo, **entities
        },
                                        strict=True,
                                        validate=False)
        if tmppath is None:
            raise RuntimeError('Unable to build path with {}'.format({
                **bidsinfo, **entities
            }))
        tmppath = Path(bidslayout.root, tmppath).resolve()
        tmppath.parent.mkdir(exist_ok=True, parents=True)
        outputfilenames[sourcename] = str(tmppath)
    outputlabels = {}
    labeloutputs = [('classified', tissue_labels_str),
                    ('transformed_atlas', atlas_labels_str),
                    ('segmented', tissue_and_atlas_labels_str),
                    ('features', tissue_labels_str)]
    if subcortical:
        labeloutputs.append(
            ('native_subcortical_atlas', subcortical_labels_str))
    for sourcename, label_str in labeloutputs:
        tmpparams = outputinfo[sourcename].copy()
        tmpparams['extension'] = 'tsv'
        tmpparams['presuffix'] = tmpparams['suffix']
        tmpparams['suffix'] = 'labels'
        tmplabelpath = bidslayout.build_path({
            **tmpparams, **entities
        },
                                             strict=True,
                                             validate=False)
        if tmplabelpath is None:
            raise RuntimeError('Unable to build path with {}'.format({
                **tmpparams, **entities
            }))
        outputlabels[sourcename] = (str(
            Path(bidslayout.root, tmplabelpath).resolve()),
                                    label_str)
    duplicate = first_nonunique(
        list(outputfilenames.values()) + list(outputlabels.values()))
    if duplicate is not None:
        raise RuntimeError(
            'Duplicate output files detected! {}'.format(duplicate))
    for sourcename in outputinfo.keys():
        node = pe.Node(ExportFile(out_file=outputfilenames[sourcename],
                                  check_extension=not debug),
                       name='write' + sourcename)
        wf.connect(inputspec, sourcename, node, 'in_file')
        if sourcename in outputlabels:
            labelnode = pe.Node(
                io.WriteFile(out_file=outputlabels[sourcename][0],
                             string=outputlabels[sourcename][1],
                             newline=''),
                'write' + sourcename + 'label')
            wf.add_nodes([labelnode])
    return wf
