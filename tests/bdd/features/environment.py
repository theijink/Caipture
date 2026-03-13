def after_scenario(context, scenario):
    tmp = getattr(context, "_tmpdir", None)
    if tmp is not None:
        tmp.cleanup()
