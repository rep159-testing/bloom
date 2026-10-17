import os
import shutil
import subprocess

import pytest

import bloom.generators.debian
from bloom.util import expand_template_em

TEMPLATES = os.path.join(os.path.dirname(bloom.generators.debian.__file__), 'templates')
GOLDEN = os.path.join(os.path.dirname(__file__), 'test_generator_data', 'rules_golden')
BUILD_TYPES = ('ament_cmake', 'cmake')
PARENTS = ['/opt/ros/mid', '/opt/ros/root']
SETUP_LINE = (
    '\tif [ -f "/opt/ros/root/setup.sh" ]; then . "/opt/ros/root/setup.sh"; fi && '
    'if [ -f "/opt/ros/mid/setup.sh" ]; then . "/opt/ros/mid/setup.sh"; fi && '
    'if [ -f "/opt/ros/child/setup.sh" ]; then . "/opt/ros/child/setup.sh"; fi && \\')


def render(build_type, prefix, parents, name):
    with open(os.path.join(TEMPLATES, build_type, 'rules.em')) as f:
        template = f.read()
    return expand_template_em(template, {
        'InstallationPrefix': prefix,
        'Name': name,
        'Package': 'ros-%s-%s' % (os.path.basename(prefix), name.replace('_', '-')),
        'ParentPrefixes': parents,
    })


@pytest.mark.parametrize('build_type', BUILD_TYPES)
def test_root_distribution_rules_unchanged(build_type):
    # golden files: the templates of bloom 0179b91, before REP 159 support
    with open(os.path.join(GOLDEN, build_type + '.rules')) as f:
        assert render(build_type, '/opt/ros/upstream', [], 'ros_workspace') == f.read()


@pytest.mark.parametrize('build_type', BUILD_TYPES)
def test_child_rules_use_the_parents(build_type):
    lines = render(build_type, '/opt/ros/child', PARENTS, 'ros_workspace').splitlines()
    assert 'export PKG_CONFIG_PATH=/opt/ros/child/lib/pkgconfig:/opt/ros/mid/lib/pkgconfig:' \
        '/opt/ros/root/lib/pkgconfig' in lines
    # all five steps source the parents first, farthest first
    assert lines.count(SETUP_LINE) == 5
    assert [line for line in lines if line.startswith('\tif [ -f') and line != SETUP_LINE] == []
    assert '\t\t-DCMAKE_PREFIX_PATH="/opt/ros/child;/opt/ros/mid;/opt/ros/root" \\' in lines
    assert '\t\t-DROS_WORKSPACE_PARENT_PREFIX_PATH="/opt/ros/mid;/opt/ros/root" \\' in lines
    if build_type == 'ament_cmake':
        assert '\t\t-DAMENT_PREFIX_PATH="/opt/ros/child;/opt/ros/mid;/opt/ros/root" \\' in lines


@pytest.mark.parametrize('build_type', BUILD_TYPES)
def test_only_ros_workspace_gets_the_parent_list(build_type):
    rules = render(build_type, '/opt/ros/child', ['/opt/ros/root'], 'upstream_c')
    assert 'ROS_WORKSPACE_PARENT_PREFIX_PATH' not in rules
    assert '-DCMAKE_PREFIX_PATH="/opt/ros/child;/opt/ros/root"' in rules


@pytest.mark.skipif(shutil.which('make') is None or shutil.which('dpkg-architecture') is None,
                    reason='needs make and dpkg-architecture')
@pytest.mark.parametrize('build_type', BUILD_TYPES)
def test_child_rules_are_a_valid_makefile(build_type, tmp_path):
    rules = tmp_path / 'rules'
    rules.write_text(render(build_type, '/opt/ros/child', PARENTS, 'ros_workspace'))
    result = subprocess.run(['make', '-n', '-f', str(rules), 'override_dh_auto_configure'],
                            cwd=str(tmp_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True)
    assert result.returncode == 0, result.stderr
    assert '-DROS_WORKSPACE_PARENT_PREFIX_PATH="/opt/ros/mid;/opt/ros/root"' in result.stdout
