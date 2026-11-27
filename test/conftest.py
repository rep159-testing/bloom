import em
import pytest


@pytest.fixture(autouse=True)
def empy3_stdout_proxy():
    """Let each test expand templates with EmPy 3.

    EmPy 3 wraps sys.stdout in a proxy on its first expansion and, from then
    on, refuses to expand ("interpreter stdout proxy lost") once sys.stdout is
    no longer that proxy. pytest's output capture and redirected_stdio() put
    their own sys.stdout back, so every expansion after the first test that
    expands one fails. Forgetting the earlier proxy lets the first expansion
    of each test install its own. EmPy 4 has no such proxy.
    """
    if hasattr(em, 'Interpreter') and hasattr(em.Interpreter, '_wasProxyInstalled'):
        em.Interpreter._wasProxyInstalled = False
