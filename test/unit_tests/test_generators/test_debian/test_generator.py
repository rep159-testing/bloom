import os

from ....utils.common import redirected_stdio

from bloom.generators.debian.generator import get_changelogs
from bloom.generators.debian.generator import format_description
from bloom.util import expand_template_em

from catkin_pkg.packages import find_packages

test_data_dir = os.path.join(os.path.dirname(__file__), 'test_generator_data')


def test_get_changelogs():
    with redirected_stdio():
        packages = dict([(pkg.name, pkg) for path, pkg in find_packages(test_data_dir).items()])
        assert 'bad_changelog_pkg' in packages
        get_changelogs(packages['bad_changelog_pkg'])


def test_unicode_templating():
    with redirected_stdio():
        packages = dict([(pkg.name, pkg) for path, pkg in find_packages(test_data_dir).items()])
        assert 'bad_changelog_pkg' in packages
        chlogs = get_changelogs(packages['bad_changelog_pkg'])
        template = "@(changelog)"
        expand_template_em(template, {'changelog': chlogs[0][2]})


def test_format_description():
    assert '' == format_description('')
    assert '.' == format_description('.')
    assert 'Word.' == format_description('Word.')
    assert 'Word' == format_description('Word')
    assert '.' == format_description(' .')
    assert '.' == format_description(' . ')
    assert 'Word.\n Other words.' == format_description('Word. Other words.')
    assert 'The first sentence, or synopsis.\n The second sentence. Part of the long description, but all in a single paragraph.' == format_description('The first sentence, or synopsis. The second sentence. Part of the long description, but all in a single paragraph.')
    assert '..' == format_description('..')
    assert 'The my_package package' == format_description('The my_package package')
    assert 'First sentence with a version nr: 2.4.5, some other text.\n And then some other text.' == format_description('First sentence with a version nr: 2.4.5, some other text. And then some other text.')
    assert 'More punctuation! This will split here.\n And the rest.' == format_description('More punctuation! This will split here. And the rest.')
    assert 'v1.2.3 with v5.3.7 and ! Split after this.\n Long description here.' == format_description('v1.2.3 with v5.3.7 and ! Split after this. Long description here.\n\n')
    # no whitespace between <p>'s, no split
    assert 'some embedded html markup.the other sentence.' == format_description('<h1>some embedded</h1>\n<p>html markup.</p><p>the other sentence.</p>')


def test_substitutions_default_to_no_parent_prefixes(tmp_path):
    from catkin_pkg.package import parse_package
    from bloom.generators.debian.generator import generate_substitutions_from_package
    (tmp_path / 'package.xml').write_text(
        '<?xml version="1.0"?>\n'
        '<package format="2">\n'
        '  <name>leaf</name>\n'
        '  <version>1.0.0</version>\n'
        '  <description>A package with no dependencies.</description>\n'
        '  <maintainer email="nobody@example.com">nobody</maintainer>\n'
        '  <license>Apache-2.0</license>\n'
        '  <export><build_type>cmake</build_type></export>\n'
        '</package>\n')
    package = parse_package(str(tmp_path))
    with redirected_stdio():
        subs = generate_substitutions_from_package(package, 'ubuntu', 'resolute', 'upstream')
    assert subs['ParentPrefixes'] == []
