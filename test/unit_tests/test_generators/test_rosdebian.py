from bloom.generators.rosdebian import get_ros_workspace_dependencies


def test_packages_depend_on_their_own_ros_workspace():
    assert get_ros_workspace_dependencies('upstream_c', 'upstream', []) == ['ros-upstream-ros-workspace']
    assert get_ros_workspace_dependencies('downstream_bin_a', 'binext', ['upstream']) == \
        ['ros-binext-ros-workspace']


def test_bootstrap_packages_get_no_ros_workspace():
    for name in ('ament_cmake_core', 'ament_package'):
        assert get_ros_workspace_dependencies(name, 'binext', ['upstream']) == []
    assert get_ros_workspace_dependencies('ros_workspace', 'upstream', []) == []


def test_child_ros_workspace_depends_on_each_parent_ros_workspace():
    assert get_ros_workspace_dependencies('ros_workspace', 'binext', ['upstream']) == \
        ['ros-upstream-ros-workspace']
    assert get_ros_workspace_dependencies('ros_workspace', 'child', ['mid', 'root']) == \
        ['ros-mid-ros-workspace', 'ros-root-ros-workspace']


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
        return ['upstream']

    monkeypatch.setattr(rosdebian, 'get_binary_import_parents', fake_parents)
    generator = _generator_for('binext')
    assert generator.get_parent_distributions() == ['upstream']
    assert generator.get_parent_distributions() == ['upstream']
    assert calls == ['binext']


def test_unreadable_parent_distribution_exits(monkeypatch):
    import pytest
    import bloom.generators.rosdebian as rosdebian
    from ...utils.common import redirected_stdio

    def failing_parents(distro, index=None):
        raise RuntimeError("parent 'upstream' cannot be read")

    monkeypatch.setattr(rosdebian, 'get_binary_import_parents', failing_parents)
    generator = _generator_for('binext')
    with redirected_stdio():
        with pytest.raises(SystemExit):
            generator.get_parent_distributions()
