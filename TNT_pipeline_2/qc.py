from . import output


def make_config(model_space,
                subcortical,
                subcortical_model_space,
                intracranial_volume):
    outfiles = output.get_outputinfo(model_space,
                                     subcortical,
                                     subcortical_model_space,
                                     intracranial_volume)
    conf = {
        "page_keys":
        ["subject", "session", "acquisition", "reconstruction", "run"],
        "page_filename_template":
        "sub-{subject}[_ses-{session}][_acq-{acquisition}][_rec-{reconstruction}][_run-{run}]_QC.html",
        "index_filename":
        "index.html",
        "patterns": {
            "bids": [
                "bids",
                "derivatives",
                {
                    "name":
                    "pndni_bids",
                    "entities": [
                        {
                            "name": "skullstripped",
                            "pattern": "[_/\\\\]+skullstripped-([a-zA-Z0-9]+)"
                        },
                        {
                            "name": "map",
                            "pattern": "[_/\\\\]+map-([a-zA-Z0-9]+)"
                        },
                        {
                            "name":
                            "presuffix",
                            "pattern":
                            "_([a-zA-Z0-9]*?)_[a-zA-Z0-9]*?\\.[^/\\\\]+$"
                        },
                        {
                            "name": "crash", "pattern": "/(crash)"
                        },
                    ]
                }
            ],
        },
        "files": {
            "features_label": {
                "pattern": "bids",
                "filter": {
                    "extension": "tsv",
                    "presuffix": outfiles["features"]["suffix"],
                    "suffix": "labels"
                }
            },
            "crashfiles": {
                "pattern": "bids",
                "filter": {
                    "crash": "crash"
                },
                "allow_multiple": True
            }
        },
        "reportlets": [
            {
                "type": "compare",
                "name1": "T1 weighted input",
                "image1": "T1",
                "name2": "non-uniformity corrected and normalized",
                "image2": "normalized",
            },
            {
                "type": "compare",
                "name1": "T1 weighted input",
                "image1": "T1",
                "name2": "Non-uniformity corrected brain",
                "image2": "nu_bet"
            },
            {
                "type": "compare",
                "name1": "T1 weighted input",
                "image1": "T1",
                "name2": "Warped model",
                "image2": "warped_model"
            },
            {
                "type": "contour",
                "name": "T1 with transformed model brain mask",
                "image": "T1",
                "labelimage": "transformed_model_brain_mask"
            },
            {
                "type": "distributions",
                "name": "Tissue distributions for classification",
                "distsfile": "features",
                "labelfile": "features_label",
            },
            {
                "type": "contour",
                "name": "Tissue segmentation",
                "image": "T1",
                "labelimage": "classified"
            },
            {
                "type": "contour",
                "name": "Lobes",
                "image": "T1",
                "labelimage": "transformed_atlas"
            },
        ]
    }
    for k, v in outfiles.items():
        conf['files'][k] = {'pattern': 'bids', 'filter': v}

    fields = ["Poor BET", "Poor regisitration", "Poor classification"]
    if subcortical:
        conf['reportlets'].extend([
            {
                "type": "compare",
                "name1": "T1 weighted input",
                "image1": "T1",
                "name2": "Transformed subcortical model",
                "image2": "warped_subcortical_model"
            },
            {
                "type": "contour",
                "name": "Sub cortical",
                "image": "T1",
                "labelimage": "native_subcortical_atlas"
            },
        ])
        fields.append("Poor subcortical registraton")
    if intracranial_volume:
        conf['reportlets'].append({
            "type": "contour",
            "name": "ICV mask",
            "image": "T1",
            "labelimage": "native_icv_mask"
        })
        fields.append("Poor ICV mask registraton")
    conf['reportlets'].extend([
        {
            "type": "crash", "name": "Errors", "crashfiles": "crashfiles"
        },
        {
            "type": "rating",
            "name": "Rating",
            "radio": {
                "name":
                "Overall",
                "options": [
                    {
                        "name": "Reject", "value": 1
                    },
                    {
                        "name": "Poor", "value": 2
                    },
                    {
                        "name": "Fair", "value": 3
                    },
                    {
                        "name": "Good", "value": 4
                    },
                    {
                        "name": "Excellent", "value": 5
                    },
                ]
            },
            "checkbox": {
                "name": "Notes", "fields": fields
            },
            "text": {
                "name": "Other"
            }
        },
    ])
    return conf
