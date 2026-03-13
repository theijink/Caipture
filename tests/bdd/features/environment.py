def after_scenario(context, scenario):
    web_server = getattr(context, "web_server", None)
    if web_server is not None:
        web_server.shutdown()
        web_server.server_close()
    tmp = getattr(context, "_tmpdir", None)
    if tmp is not None:
        tmp.cleanup()
