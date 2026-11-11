from bloom.generators.rosdebian import get_workspace_dependencies


def test_packages_depend_on_their_own_ros_workspace():
    assert get_workspace_dependencies('upstream_c', 'upstream', 'ros_workspace', []) == \
        ['ros-upstream-ros-workspace']
    assert get_workspace_dependencies('downstream_bin_a', 'binext', 'ros_workspace',
                                      [('upstream', 'ros_workspace')]) == ['ros-binext-ros-workspace']


def test_bootstrap_packages_get_no_ros_workspace():
    for name in ('ament_cmake_core', 'ament_package'):
        assert get_workspace_dependencies(name, 'binext', 'ros_workspace',
                                          [('upstream', 'ros_workspace')]) == []
    assert get_workspace_dependencies('ros_workspace', 'upstream', 'ros_workspace', []) == []


def test_child_ros_workspace_depends_on_each_parent_ros_workspace():
    assert get_workspace_dependencies('ros_workspace', 'binext', 'ros_workspace',
                                      [('upstream', 'ros_workspace')]) == ['ros-upstream-ros-workspace']
    assert get_workspace_dependencies('ros_workspace', 'child', 'ros_workspace',
                                      [('mid', 'ros_workspace'), ('root', 'ros_workspace')]) == \
        ['ros-mid-ros-workspace', 'ros-root-ros-workspace']


def test_packages_depend_on_the_named_workspace_package():
    assert get_workspace_dependencies('upstream_c', 'srcext', 'ros_workspace_shell', []) == \
        ['ros-srcext-ros-workspace-shell']
    assert get_workspace_dependencies('ros_workspace_shell', 'srcext', 'ros_workspace_shell', []) == []


def test_only_ros_workspace_exempts_its_build_dependencies():
    # ros_workspace_shell is built without ament, so ament packages use it
    for name in ('ament_cmake_core', 'ament_package', 'ros_workspace'):
        assert get_workspace_dependencies(name, 'srcext', 'ros_workspace_shell', []) == \
            ['ros-srcext-ros-workspace-shell']


def test_child_workspace_package_depends_on_each_parent_own_workspace_package():
    parents = [('mid', 'ros_workspace'), ('root', 'ros_workspace_shell')]
    assert get_workspace_dependencies('ros_workspace', 'child', 'ros_workspace', parents) == \
        ['ros-mid-ros-workspace', 'ros-root-ros-workspace-shell']
    assert get_workspace_dependencies('ros_workspace_shell', 'child', 'ros_workspace_shell', parents) == \
        ['ros-mid-ros-workspace', 'ros-root-ros-workspace-shell']


def _generator_for(distro):
    from bloom.generators.rosdebian import RosDebianGenerator
    generator = RosDebianGenerator()
    generator.rosdistro = distro
    return generator


def test_parent_distributions_are_walked_once(monkeypatch):
    import bloom.generators.rosdebian as rosdebian
    calls = []

    def fake_parents(distro, index=None):
        calls.append(distro)
        return [('upstream', 'ros_workspace')]

    monkeypatch.setattr(rosdebian, 'get_binary_import_parent_workspace_packages', fake_parents)
    generator = _generator_for('binext')
    assert generator.get_parent_distributions() == [('upstream', 'ros_workspace')]
    assert generator.get_parent_distributions() == [('upstream', 'ros_workspace')]
    assert calls == ['binext']


def test_unreadable_parent_distribution_exits(monkeypatch):
    import pytest
    import bloom.generators.rosdebian as rosdebian
    from ...utils.common import redirected_stdio

    def failing_parents(distro, index=None):
        raise RuntimeError("parent 'upstream' cannot be read")

    monkeypatch.setattr(rosdebian, 'get_binary_import_parent_workspace_packages', failing_parents)
    generator = _generator_for('binext')
    with redirected_stdio():
        with pytest.raises(SystemExit):
            generator.get_parent_distributions()


def test_workspace_package_is_read_once(monkeypatch):
    import bloom.generators.rosdebian as rosdebian
    calls = []

    def fake_workspace_package(distro, index=None):
        calls.append(distro)
        return 'ros_workspace_shell'

    monkeypatch.setattr(rosdebian, 'get_workspace_package', fake_workspace_package)
    generator = _generator_for('srcext')
    assert generator.get_workspace_package() == 'ros_workspace_shell'
    assert generator.get_workspace_package() == 'ros_workspace_shell'
    assert calls == ['srcext']


def test_unreadable_workspace_package_exits(monkeypatch):
    import pytest
    import bloom.generators.rosdebian as rosdebian
    from ...utils.common import redirected_stdio

    def failing_workspace_package(distro, index=None):
        raise RuntimeError("No distribution files listed for distribution 'srcext'")

    monkeypatch.setattr(rosdebian, 'get_workspace_package', failing_workspace_package)
    generator = _generator_for('srcext')
    with redirected_stdio():
        with pytest.raises(SystemExit):
            generator.get_workspace_package()
