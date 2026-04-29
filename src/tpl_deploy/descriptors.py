
class classproperty:
    def __init__(self, fget):
        self.fget = fget
        self.fset = None

    def __get__(self, _, owner):
        return self.fget(owner)

    def setter(self, fset):
        self.fset = fset
        return self

class ClassPropertyMeta(type):
    def __setattr__(cls, name, value):
        attr = cls.__dict__.get(name)
        if isinstance(attr, classproperty) and attr.fset is not None:
            attr.fset(cls, value)
            return
        super().__setattr__(name, value)
