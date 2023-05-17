class Plugin():
    """The base class to inherit a plugin from."""
    def check(self):
        raise NotImplementedError('Method not implemented')
