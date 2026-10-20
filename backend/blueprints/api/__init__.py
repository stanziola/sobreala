from .core import bp  # noqa: F401

# Cada archivo declara sus rutas sobre `bp` al importarse.
from . import account  # noqa: F401,E402
from . import contacts  # noqa: F401,E402
from . import templates  # noqa: F401,E402
from . import emails  # noqa: F401,E402
from . import campaigns  # noqa: F401,E402
