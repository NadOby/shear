"""The failure of the hosted pipeline's admission boundary."""

from __future__ import annotations


class AdmissionRejected(Exception):
    """No authorized executable artifact is available for this request.

    Deliberately outside ``LanguageError`` and ``CellContentRejected``: an
    admission failure is a host failure. A program's ``catch`` cannot see it
    and a corpus step that expects a language error cannot be satisfied by it.
    """


class UnsupportedOperation(AdmissionRejected):
    """The SHEAR compiler does not lower this node's operation.

    A program is still prepared without such a node; running it fails closed.
    """
