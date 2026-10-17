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
