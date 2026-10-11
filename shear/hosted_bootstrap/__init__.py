"""The hosted bootstrap pipeline (docs/hosted_pipeline.md, roadmap task 30).

SHEAR source goes through host parsing and graph construction, the SHEAR
compiler, authenticated admission and execution on the host machine. The
public boundary is ``HostedSession``; ``main`` is the documented command.
"""

from .command import main
from .errors import AdmissionRejected, UnsupportedOperation
from .generations import GenerationReport
from .session import HostedSession, StagedEdit

__all__ = [
    "AdmissionRejected",
    "GenerationReport",
    "HostedSession",
    "StagedEdit",
    "UnsupportedOperation",
    "main",
]
