import os

import pytest
import rosdistro
import yaml

from bloom.rosdistro_api import get_binary_import_parent_workspace_packages
from bloom.rosdistro_api import get_binary_import_parents
from bloom.rosdistro_api import get_workspace_package


def write_index(root, distributions, workspace_packages=None):
    """Write an index of format-3 distributions with only `extends` filled in.

    `distributions` maps a name to its list of `extends` entries (or None);
    `workspace_packages` maps a name to its `workspace_package`, if any.
    """
    os.makedirs(str(root))
    index = {'type': 'index', 'version': 4, 'distributions': {}}
    for name, extends in distributions.items():
        os.makedirs(str(root / name))
        data = {
            'type': 'distribution',
            'version': 3,
            'release_platforms': {'ubuntu': ['resolute']},
            'repositories': {},
        }
        if extends:
            data['extends'] = extends
        if workspace_packages and name in workspace_packages:
            data['workspace_package'] = workspace_packages[name]
        with open(str(root / name / 'distribution.yaml'), 'w') as f:
            yaml.safe_dump(data, f)
        index['distributions'][name] = {
            'distribution': ['%s/distribution.yaml' % name],
            'distribution_status': 'active',
            'distribution_type': 'ros2',
            'python_version': 3,
        }
    with open(str(root / 'index-v4.yaml'), 'w') as f:
        yaml.safe_dump(index, f)
    return 'file://%s' % (root / 'index-v4.yaml')


def bi(name, index_url=None):
    ext = {'distro_name': name, 'extension_method': 'binary_import'}
    if index_url:
        ext['index_url'] = index_url
    return [ext]


def sr(name):
    return [{'distro_name': name, 'extension_method': 'source_rebuild'}]


def parents(tmp_path, distributions, distro):
    index = rosdistro.get_index(write_index(tmp_path / 'index', distributions))
    return get_binary_import_parents(distro, index)


def test_root_has_no_parents(tmp_path):
    assert parents(tmp_path, {'upstream': None}, 'upstream') == []


def test_one_binary_import_parent(tmp_path):
    assert parents(tmp_path, {'upstream': None, 'binext': bi('upstream')}, 'binext') == ['upstream']


def test_chain_is_nearest_first(tmp_path):
    distributions = {'root': None, 'mid': bi('root'), 'child': bi('mid')}
    assert parents(tmp_path, distributions, 'child') == ['mid', 'root']


def test_source_rebuild_edge_stops_the_walk(tmp_path):
    distributions = {'root': None, 'srcext': sr('root'), 'child': bi('srcext')}
    assert parents(tmp_path, distributions, 'child') == ['srcext']
    assert parents(tmp_path / 'again', distributions, 'srcext') == []


def test_parent_in_another_index(tmp_path):
    other = write_index(tmp_path / 'other', {'upstream': None})
    distributions = {'binext': bi('upstream', index_url=other)}
    assert parents(tmp_path, distributions, 'binext') == ['upstream']


def test_several_parents_keep_declared_order(tmp_path):
    distributions = {
        'root': None, 'p1': bi('root'), 'p2': bi('root'),
        'child': bi('p1') + bi('p2'),
    }
    assert parents(tmp_path, distributions, 'child') == ['p1', 'root', 'p2']


def test_missing_parent_raises(tmp_path):
    with pytest.raises(RuntimeError, match="'nowhere', which 'child' extends"):
        parents(tmp_path, {'child': bi('nowhere')}, 'child')


def test_unreachable_parent_index_raises(tmp_path):
    missing = 'file://%s' % (tmp_path / 'missing' / 'index-v4.yaml')
    with pytest.raises(RuntimeError, match="'upstream', which 'binext' extends"):
        parents(tmp_path, {'binext': bi('upstream', index_url=missing)}, 'binext')


def test_cycle_raises(tmp_path):
    with pytest.raises(RuntimeError, match="Cycle in 'extends': a -> b -> a"):
        parents(tmp_path, {'a': bi('b'), 'b': bi('a')}, 'a')


def test_get_binary_package_name_fallback():
    from bloom.rosdistro_api import get_binary_package_name
    assert get_binary_package_name('foxy', 'my_package') == 'ros-foxy-my-package'


def test_get_install_prefix_fallback():
    from bloom.rosdistro_api import get_install_prefix
    assert get_install_prefix('foxy') == '/opt/ros/foxy'


def test_get_binary_package_name_and_install_rule(monkeypatch):
    from bloom.rosdistro_api import get_binary_package_name, get_install_prefix

    class MockDistFile:
        install_rule = '/opt/vendor/{distro}'

        def get_binary_package_name(self, pkg):
            return 'vendor-custom-' + pkg.replace('_', '-')

    monkeypatch.setattr('bloom.rosdistro_api.get_distribution_file', lambda d: MockDistFile())
    assert get_binary_package_name('composable', 'upstream_a') == 'vendor-custom-upstream-a'
    assert get_install_prefix('composable') == '/opt/vendor/composable'


def test_get_install_prefix_delegates_to_dist_file(monkeypatch):
    from bloom.rosdistro_api import get_install_prefix

    class MockDistFileWithMethod:
        def get_install_prefix(self, pkg_name=None):
            return '/opt/custom/prefix'

    monkeypatch.setattr('bloom.rosdistro_api.get_distribution_file', lambda d: MockDistFileWithMethod())
    assert get_install_prefix('my_distro') == '/opt/custom/prefix'


def test_workspace_package_defaults_to_ros_workspace(tmp_path):
    index = rosdistro.get_index(write_index(tmp_path / 'index', {'upstream': None}))
    assert get_workspace_package('upstream', index) == 'ros_workspace'


def test_workspace_package_from_the_distribution_file(tmp_path):
    index = rosdistro.get_index(write_index(
        tmp_path / 'index', {'upstream': None, 'srcext': sr('upstream')},
        {'srcext': 'ros_workspace_shell'}))
    assert get_workspace_package('srcext', index) == 'ros_workspace_shell'
    # not inherited: the parent keeps its own
    assert get_workspace_package('upstream', index) == 'ros_workspace'


def test_workspace_package_of_a_missing_distribution_raises(tmp_path):
    index = rosdistro.get_index(write_index(tmp_path / 'index', {'upstream': None}))
    with pytest.raises(RuntimeError):
        get_workspace_package('nowhere', index)


def test_parents_come_with_their_own_workspace_package(tmp_path):
    other = write_index(tmp_path / 'other', {'root': None}, {'root': 'ros_workspace_shell'})
    distributions = {'mid': bi('root', index_url=other), 'child': bi('mid')}
    index = rosdistro.get_index(write_index(tmp_path / 'index', distributions))
    assert get_binary_import_parent_workspace_packages('child', index) == \
        [('mid', 'ros_workspace'), ('root', 'ros_workspace_shell')]
