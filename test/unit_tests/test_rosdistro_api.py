import os

import pytest
import rosdistro
import yaml

from bloom.rosdistro_api import get_binary_import_parents


def write_index(root, distributions):
    """Write an index of format-3 distributions with only `extends` filled in.

    `distributions` maps a name to its list of `extends` entries (or None).
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
