def _update_workdir(wf, workdir):
    if workdir is None:
        return
    if not workdir.exists():
        raise FileNotFoundError('Specified working directory does not exist')
    wf.base_dir = str(workdir)
